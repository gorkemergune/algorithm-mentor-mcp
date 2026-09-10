"""MCP server giriş noktası — stdio transport üzerinde 9 v1 tool'u yayınlar.

Mimari (CLAUDE.md): resmi `mcp` Python SDK'sı (v2), stdio transport.
Sunucu açılışında **tek** SQLite bağlantısı açılır ve problem/konu verisi
bir kez yüklenir; her tool çağrısı bu hazır bağlamı kullanır — tool'lar
kendi bağlantılarını açmaz, veriyi diskten tekrar okumaz.

Tool'ların fırlattığı `LookupError` / `ValueError` gibi iç hatalar MCP
hata cevabına çevrilir: host'a stack trace değil, anlamlı tek satırlık bir
mesaj gider.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp import types

from src.domain.problem import Problem, load_problems
from src.domain.topics import load_topics
from src.storage import sqlite as db
from src.tools.assess_level import assess_level
from src.tools.explain_approach import explain_approach
from src.tools.get_next_topic import get_next_topic
from src.tools.get_problem import get_problem
from src.tools.get_reference_approach import get_reference_approach
from src.tools.hint import hint
from src.tools.review_solution import review_solution
from src.tools.submit_solution import submit_solution
from src.tools.update_profile import update_profile

SERVER_NAME = "algorithm-mentor"
SERVER_VERSION = "0.1.0"

LOCALE_SCHEMA = {"type": "string", "enum": ["tr", "en"]}


@dataclass(frozen=True)
class MentorContext:
    """Sunucu ömrü boyunca yaşayan hazır bağlam."""

    connection: sqlite3.Connection
    problems: tuple[Problem, ...]
    topics: dict[str, tuple[str, ...]]

    def preferred_language(self) -> str | None:
        """Profildeki dil; profil yoksa `None` (tool'lar EN'e düşer)."""
        profile = db.get_profile(self.connection)
        return profile["preferred_language"] if profile is not None else None


def build_context(db_path: Path | str | None = None) -> MentorContext:
    """Bağlantıyı açar, statik veriyi bir kez yükler."""
    return MentorContext(
        connection=db.connect(db_path),
        problems=load_problems(),
        topics=load_topics(),
    )


# --- tool tanımları (şemalar docs/TOOLS.md ile birebir) ---------------------


def _tool(name: str, description: str, properties: dict, required: list[str], output: dict) -> types.Tool:
    return types.Tool(
        name=name,
        description=description,
        input_schema={
            "type": "object",
            "properties": properties,
            "required": required,
        },
        output_schema={"type": "object", "properties": output},
    )


TOOLS: tuple[types.Tool, ...] = (
    _tool(
        "assess_level",
        "Öğrencinin başlangıç profilini kurar: her konuyu 0.0 ile seed'ler, "
        "seviyeyi belirler ve başlanacak konuyu önerir.",
        {
            "preferred_language": {
                **LOCALE_SCHEMA,
                "description": "Kullanıcının konuştuğu dil; problem/hint metinlerinin varsayılanı.",
                "default": "tr",
            },
            "retake": {
                "type": "boolean",
                "description": "Mevcut profili yeniden değerlendir (skorlar sıfırlanır, geçmiş kalır).",
                "default": False,
            },
        },
        [],
        {
            "estimated_level": {"type": "string"},
            "topic_estimates": {"type": "object"},
            "recommended_start_topic": {"type": "string"},
        },
    ),
    _tool(
        "get_problem",
        "Konuya ve zorluk seviyesine göre bir problem döndürür. Gizli test "
        "case'ler, hint'ler ve referans yaklaşım çıktıya girmez.",
        {
            "topic": {"type": "string", "description": "Konu, örn. 'arrays', 'graphs'."},
            "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
            "language": {
                "type": "string",
                "enum": ["python"],
                "description": "Programlama dili (v1'de yalnız python).",
                "default": "python",
            },
            "locale": {**LOCALE_SCHEMA, "description": "Problem metninin dili; boşsa profilden."},
        },
        ["topic", "difficulty"],
        {
            "problem_id": {"type": "string"},
            "title": {"type": "string"},
            "prompt": {"type": "string"},
            "starter_code": {"type": "string"},
            "test_cases": {"type": "array"},
            "locale": {"type": "string"},
        },
    ),
    _tool(
        "submit_solution",
        "Kullanıcının kodunu sandbox'ta çalıştırır ve problemin test "
        "case'lerinden (gizliler dahil) geçirir.",
        {
            "code": {"type": "string", "description": "Kullanıcının solve fonksiyonunu içeren kod."},
            "problem_id": {"type": "string"},
            "language": {"type": "string", "enum": ["python"], "default": "python"},
        },
        ["code", "problem_id"],
        {
            "passed": {"type": "boolean"},
            "test_results": {"type": "array"},
            "runtime_ms": {"type": "integer"},
            "error": {"type": ["string", "null"]},
        },
    ),
    _tool(
        "hint",
        "Kademeli ipucu verir; deneme numarası arttıkça ipucu netleşir. "
        "Direkt çözümü vermez.",
        {
            "problem_id": {"type": "string"},
            "attempt_number": {
                "type": "integer",
                "minimum": 1,
                "description": "Kaçıncı deneme — ipucu seviyesini belirler.",
            },
            "locale": {**LOCALE_SCHEMA, "description": "Boşsa profildeki dil kullanılır."},
        },
        ["problem_id", "attempt_number"],
        {
            "hint_level": {"type": "integer"},
            "hint_text": {"type": "string"},
            "locale": {"type": "string"},
        },
    ),
    _tool(
        "explain_approach",
        "Kullanıcının sözlü anlatımını alındı olarak onaylar. Doğruluğu "
        "yargılamaz ve metni hiçbir yere kalıcı yazmaz.",
        {
            "problem_id": {"type": "string"},
            "explanation": {"type": "string", "description": "Kullanıcının doğal dildeki anlatımı."},
        },
        ["problem_id", "explanation"],
        {"received": {"type": "boolean"}, "problem_id": {"type": "string"}},
    ),
    _tool(
        "get_reference_approach",
        "Problemin gizli referans yaklaşımını döner (etiketler + özet); "
        "host'un sözlü anlatımı karşılaştırması için.",
        {
            "problem_id": {"type": "string"},
            "locale": {**LOCALE_SCHEMA, "description": "Özetin dili; boşsa profilden."},
        },
        ["problem_id"],
        {
            "approach_tags": {"type": "array", "items": {"type": "string"}},
            "approach_summary": {"type": "string"},
            "locale": {"type": "string"},
        },
    ),
    _tool(
        "review_solution",
        "Denemenin skorunu SABİT tablodan üretir ve hata tipini "
        "sınıflandırır. Host buraya ham skor gönderemez.",
        {
            "problem_id": {"type": "string"},
            "attempt_type": {"type": "string", "enum": ["code", "explanation"]},
            "test_results": {
                "type": ["object", "null"],
                "description": "attempt_type='code' ise submit_solution çıktısı.",
            },
            "hints_used": {"type": "integer", "minimum": 0, "default": 0},
            "reference_match": {
                "type": ["boolean", "null"],
                "description": "attempt_type='explanation' ise host'un doğru/yanlış kararı.",
            },
        },
        ["problem_id", "attempt_type"],
        {
            "score": {"type": "number"},
            "evidence": {"type": "array", "items": {"type": "string"}},
            "mistake_type": {"type": "string"},
            "suggested_topic_reinforcement": {"type": ["string", "null"]},
        },
    ),
    _tool(
        "update_profile",
        "Denemeyi profile işler: skoru doğrular, EMA uygular, kanıtı ve "
        "denemeyi kaydeder. Yalnızca review_solution'ın ürettiği skoru kabul eder.",
        {
            "topic": {"type": "string"},
            "problem_id": {"type": "string"},
            "score": {
                "type": "number",
                "description": "Yalnızca review_solution.score (1.0/0.8/0.6/0.5/0.2).",
            },
            "evidence": {"type": "array", "items": {"type": "string"}},
            "mistake_type": {"type": ["string", "null"]},
            "hints_used": {"type": "integer", "minimum": 0, "default": 0},
        },
        ["topic", "problem_id", "score"],
        {
            "topic_scores": {"type": "object"},
            "recent_evidence": {"type": "object"},
            "level": {"type": "string"},
        },
    ),
    _tool(
        "get_next_topic",
        "Sıradaki konuyu önerir: ön koşul eşiği, en düşük skor ve sıkışma "
        "koruması kurallarıyla. Profili yalnızca okur.",
        {},
        [],
        {
            "recommended_topic": {"type": "string"},
            "reason_code": {"type": "string"},
            "reason": {"type": "string"},
            "locale": {"type": "string"},
        },
    ),
)


# --- tool çağrıları ---------------------------------------------------------


def _call_assess_level(context: MentorContext, arguments: dict) -> dict:
    return assess_level(
        arguments.get("preferred_language", "tr"),
        arguments.get("retake", False),
        connection=context.connection,
        topics=context.topics,
    )


def _call_get_problem(context: MentorContext, arguments: dict) -> dict:
    return get_problem(
        arguments["topic"],
        arguments["difficulty"],
        arguments.get("language", "python"),
        arguments.get("locale"),
        problems=context.problems,
        preferred_language=context.preferred_language(),
    )


def _call_submit_solution(context: MentorContext, arguments: dict) -> dict:
    return submit_solution(
        arguments["code"],
        arguments["problem_id"],
        arguments.get("language", "python"),
        problems=context.problems,
    )


def _call_hint(context: MentorContext, arguments: dict) -> dict:
    return hint(
        arguments["problem_id"],
        arguments["attempt_number"],
        arguments.get("locale"),
        problems=context.problems,
        connection=context.connection,
    )


def _call_explain_approach(context: MentorContext, arguments: dict) -> dict:
    return explain_approach(
        arguments["problem_id"],
        arguments["explanation"],
        problems=context.problems,
    )


def _call_get_reference_approach(context: MentorContext, arguments: dict) -> dict:
    return get_reference_approach(
        arguments["problem_id"],
        arguments.get("locale"),
        problems=context.problems,
        connection=context.connection,
    )


def _call_review_solution(context: MentorContext, arguments: dict) -> dict:
    return review_solution(
        arguments["problem_id"],
        arguments["attempt_type"],
        arguments.get("test_results"),
        arguments.get("hints_used", 0),
        arguments.get("reference_match"),
        problems=context.problems,
    )


def _call_update_profile(context: MentorContext, arguments: dict) -> dict:
    return update_profile(
        arguments["topic"],
        arguments["problem_id"],
        arguments["score"],
        arguments.get("evidence"),
        arguments.get("mistake_type"),
        arguments.get("hints_used", 0),
        connection=context.connection,
    )


def _call_get_next_topic(context: MentorContext, arguments: dict) -> dict:
    return get_next_topic(connection=context.connection, topics=context.topics)


HANDLERS: dict[str, Callable[[MentorContext, dict], dict]] = {
    "assess_level": _call_assess_level,
    "get_problem": _call_get_problem,
    "submit_solution": _call_submit_solution,
    "hint": _call_hint,
    "explain_approach": _call_explain_approach,
    "get_reference_approach": _call_get_reference_approach,
    "review_solution": _call_review_solution,
    "update_profile": _call_update_profile,
    "get_next_topic": _call_get_next_topic,
}


def dispatch(context: MentorContext, name: str, arguments: dict | None) -> dict:
    """Tool'u çağırır. Bilinmeyen isim `LookupError`, eksik argüman `ValueError`."""
    handler = HANDLERS.get(name)
    if handler is None:
        raise LookupError(f"unknown tool: {name!r}")
    try:
        return handler(context, arguments or {})
    except KeyError as missing:
        raise ValueError(f"missing required argument: {missing.args[0]!r}") from missing


def call_tool(context: MentorContext, name: str, arguments: dict | None) -> types.CallToolResult:
    """Tool sonucunu MCP cevabına çevirir; iç hataları hata cevabına indirger."""
    try:
        payload = dispatch(context, name, arguments)
    except (LookupError, ValueError) as error:
        return _error_result(f"{type(error).__name__}: {error}")
    except Exception as error:  # noqa: BLE001 - host'a stack trace sızmasın
        return _error_result(f"internal error while running {name!r}: {error}")

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structured_content=payload,
    )


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        is_error=True,
    )


# --- sunucu ----------------------------------------------------------------


def build_server(context: MentorContext) -> Server:
    """Tool'ları kayıtlı, verilen bağlamı kullanan bir MCP sunucusu kurar."""

    async def on_list_tools(request_context: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=list(TOOLS))

    async def on_call_tool(
        request_context: Any,
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        return call_tool(context, params.name, params.arguments)

    return Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=(
            "Algoritma mentörü: seviye tespiti, problem verme, kod çalıştırma, "
            "kademeli ipucu ve profil takibi. Skorlar sunucudaki sabit tablodan "
            "gelir; asla kendin bir mastery sayısı gönderme."
        ),
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def serve(db_path: Path | str | None = None) -> None:
    """stdio üzerinde sunucuyu çalıştırır."""
    context = build_context(db_path)
    server = build_server(context)
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        context.connection.close()


def main() -> None:
    anyio.run(serve)


if __name__ == "__main__":
    main()
