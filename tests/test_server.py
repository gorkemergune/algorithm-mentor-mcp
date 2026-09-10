"""MCP sunucusunun uçtan uca testleri.

Zincirler gerçek problem verisiyle (`arrays_012`) ve gerçek MCP protokolü
üzerinden çalıştırılır: bellek içi client↔server oturumu kurulur, tool'lar
host'un çağıracağı şekilde çağrılır.
"""

from contextlib import asynccontextmanager

import anyio
import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from src.server import TOOLS, build_context, build_server, call_tool
from src.storage import sqlite as db

TWO_SUM = """
def solve(nums, target):
    seen = {}
    for index, value in enumerate(nums):
        if target - value in seen:
            return [seen[target - value], index]
        seen[value] = index
    return []
"""

WRONG_TWO_SUM = """
def solve(nums, target):
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target and nums[i] != nums[j]:
                return [i, j]
    return []
"""


@asynccontextmanager
async def mcp_session(context):
    """Bellek içi transport üzerinde gerçek bir client oturumu açar."""
    server = build_server(context)
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        async with anyio.create_task_group() as task_group:

            async def run_server() -> None:
                await server.run(
                    server_read, server_write, server.create_initialization_options()
                )

            task_group.start_soon(run_server)
            async with ClientSession(client_read, client_write) as session:
                await session.initialize()
                yield session
            task_group.cancel_scope.cancel()


def structured(result):
    assert result.is_error is not True, result.content[0].text
    return result.structured_content


class TestToolRegistration:
    def test_all_nine_v1_tools_are_registered(self):
        assert {tool.name for tool in TOOLS} == {
            "assess_level",
            "get_problem",
            "submit_solution",
            "hint",
            "explain_approach",
            "get_reference_approach",
            "review_solution",
            "update_profile",
            "get_next_topic",
        }

    def test_every_tool_has_schemas_and_a_description(self):
        for tool in TOOLS:
            assert tool.description
            assert tool.input_schema["type"] == "object"
            assert tool.output_schema is not None

    def test_required_arguments_match_the_spec(self):
        required = {tool.name: set(tool.input_schema.get("required", [])) for tool in TOOLS}

        assert required["get_problem"] == {"topic", "difficulty"}
        assert required["submit_solution"] == {"code", "problem_id"}
        assert required["hint"] == {"problem_id", "attempt_number"}
        assert required["review_solution"] == {"problem_id", "attempt_type"}
        assert required["update_profile"] == {"topic", "problem_id", "score"}
        assert required["explain_approach"] == {"problem_id", "explanation"}
        assert required["assess_level"] == set()
        assert required["get_next_topic"] == set()

    def test_tools_are_listed_over_the_protocol(self):
        async def scenario():
            context = build_context(":memory:")
            async with mcp_session(context) as session:
                listed = await session.list_tools()
                return {tool.name for tool in listed.tools}

        assert anyio.run(scenario) == {tool.name for tool in TOOLS}


class TestContextIsShared:
    def test_one_connection_and_one_data_load_serve_every_tool(self):
        context = build_context(":memory:")

        call_tool(context, "assess_level", {"preferred_language": "tr"})
        call_tool(context, "update_profile", {
            "topic": "arrays", "problem_id": "arrays_012", "score": 1.0, "evidence": ["kanıt"]
        })

        # Tool'lar kendi bağlantılarını açsaydı bu yazma görünmezdi.
        assert db.get_topic_scores(context.connection)["arrays"] == pytest.approx(0.3)
        assert context.problems and context.topics

    def test_profile_language_flows_into_get_problem(self):
        context = build_context(":memory:")
        call_tool(context, "assess_level", {"preferred_language": "tr"})

        problem = structured(call_tool(context, "get_problem", {
            "topic": "arrays", "difficulty": "easy"
        }))

        assert problem["locale"] == "tr"
        assert problem["title"] == "İki Sayının Toplamı"


class TestErrorTranslation:
    def test_unknown_problem_becomes_an_error_result(self):
        context = build_context(":memory:")
        result = call_tool(context, "get_problem", {"topic": "quantum", "difficulty": "easy"})

        assert result.is_error is True
        assert "quantum" in result.content[0].text
        assert "Traceback" not in result.content[0].text

    def test_missing_argument_is_reported_by_name(self):
        context = build_context(":memory:")
        result = call_tool(context, "hint", {"problem_id": "arrays_012"})

        assert result.is_error is True
        assert "attempt_number" in result.content[0].text

    def test_unknown_tool_is_reported(self):
        context = build_context(":memory:")
        result = call_tool(context, "teleport", {})

        assert result.is_error is True
        assert "teleport" in result.content[0].text

    def test_host_invented_score_is_refused(self):
        context = build_context(":memory:")
        call_tool(context, "assess_level", {})

        result = call_tool(context, "update_profile", {
            "topic": "arrays", "problem_id": "arrays_012", "score": 0.97, "evidence": []
        })

        assert result.is_error is True
        assert "review_solution" in result.content[0].text

    def test_update_before_assess_is_refused(self):
        context = build_context(":memory:")
        result = call_tool(context, "update_profile", {
            "topic": "arrays", "problem_id": "arrays_012", "score": 1.0, "evidence": []
        })

        assert result.is_error is True
        assert "assess_level" in result.content[0].text

    def test_errors_travel_over_the_protocol(self):
        async def scenario():
            context = build_context(":memory:")
            async with mcp_session(context) as session:
                return await session.call_tool("get_problem", {
                    "topic": "quantum", "difficulty": "easy"
                })

        result = anyio.run(scenario)
        assert result.is_error is True


class TestCodeAttemptChain:
    def test_assess_to_next_topic_over_the_protocol(self):
        async def scenario():
            context = build_context(":memory:")
            async with mcp_session(context) as session:
                assessment = structured(await session.call_tool(
                    "assess_level", {"preferred_language": "tr"}
                ))

                problem = structured(await session.call_tool("get_problem", {
                    "topic": assessment["recommended_start_topic"],
                    "difficulty": "easy",
                }))

                submission = structured(await session.call_tool("submit_solution", {
                    "code": TWO_SUM,
                    "problem_id": problem["problem_id"],
                }))

                review = structured(await session.call_tool("review_solution", {
                    "problem_id": problem["problem_id"],
                    "attempt_type": "code",
                    "test_results": submission,
                    "hints_used": 0,
                }))

                profile = structured(await session.call_tool("update_profile", {
                    "topic": "arrays",
                    "problem_id": problem["problem_id"],
                    "score": review["score"],
                    "evidence": review["evidence"],
                    "mistake_type": review["mistake_type"],
                    "hints_used": 0,
                }))

                nxt = structured(await session.call_tool("get_next_topic", {}))
                return assessment, problem, submission, review, profile, nxt

        assessment, problem, submission, review, profile, nxt = anyio.run(scenario)

        # Her adım bir sonrakini besliyor mu?
        assert assessment["recommended_start_topic"] == "arrays"
        assert problem["problem_id"] == "arrays_012"
        assert problem["locale"] == "tr"
        assert submission["passed"] is True
        assert review["score"] == 1.0
        assert review["evidence"] == ["Correct algorithm, no hints needed"]
        assert review["mistake_type"] == "none"
        assert review["suggested_topic_reinforcement"] is None
        assert profile["topic_scores"]["arrays"] == pytest.approx(0.3)
        assert profile["recent_evidence"]["arrays"] == ["Correct algorithm, no hints needed"]
        assert profile["level"] == "beginner"
        assert nxt["recommended_topic"] in assessment["topic_estimates"]
        assert nxt["locale"] == "tr"

    def test_failing_edge_case_flows_through_as_missing_edge_case(self):
        context = build_context(":memory:")
        call_tool(context, "assess_level", {"preferred_language": "en"})

        submission = structured(call_tool(context, "submit_solution", {
            "code": WRONG_TWO_SUM, "problem_id": "arrays_012"
        }))
        review = structured(call_tool(context, "review_solution", {
            "problem_id": "arrays_012",
            "attempt_type": "code",
            "test_results": submission,
            "hints_used": 2,
        }))
        profile = structured(call_tool(context, "update_profile", {
            "topic": "arrays",
            "problem_id": "arrays_012",
            "score": review["score"],
            "evidence": review["evidence"],
            "mistake_type": review["mistake_type"],
            "hints_used": 2,
        }))

        # Gizli case ([3,3], 6) edge_case: true olarak etiketli.
        assert submission["passed"] is False
        assert submission["test_results"][2]["passed"] is False
        assert review["mistake_type"] == "missing_edge_case"
        assert review["score"] == 0.2
        assert profile["recent_evidence"]["arrays"] == [
            "Approach correct but missing edge case handling"
        ]
        assert db.get_attempts(context.connection)[0]["hints_used"] == 2

    def test_hints_lower_the_score_along_the_chain(self):
        context = build_context(":memory:")
        call_tool(context, "assess_level", {})

        first_hint = structured(call_tool(context, "hint", {
            "problem_id": "arrays_012", "attempt_number": 1
        }))
        submission = structured(call_tool(context, "submit_solution", {
            "code": TWO_SUM, "problem_id": "arrays_012"
        }))
        review = structured(call_tool(context, "review_solution", {
            "problem_id": "arrays_012",
            "attempt_type": "code",
            "test_results": submission,
            "hints_used": 1,
        }))

        assert first_hint["hint_level"] == 1
        assert review["score"] == 0.8
        assert review["evidence"] == ["Correct algorithm, needed one hint"]
        assert review["suggested_topic_reinforcement"] == "arrays"


class TestExplanationChain:
    def test_explain_to_update_over_the_protocol(self):
        async def scenario():
            context = build_context(":memory:")
            async with mcp_session(context) as session:
                await session.call_tool("assess_level", {"preferred_language": "tr"})

                received = structured(await session.call_tool("explain_approach", {
                    "problem_id": "arrays_012",
                    "explanation": "Her elemanda tamamlayıcıyı hashmap'te ararım.",
                }))

                reference = structured(await session.call_tool("get_reference_approach", {
                    "problem_id": "arrays_012",
                }))

                # Host, anlatımı referansla karşılaştırıp boolean üretir.
                reference_match = "hashmap" in reference["approach_tags"]

                review = structured(await session.call_tool("review_solution", {
                    "problem_id": "arrays_012",
                    "attempt_type": "explanation",
                    "reference_match": reference_match,
                }))

                profile = structured(await session.call_tool("update_profile", {
                    "topic": "arrays",
                    "problem_id": "arrays_012",
                    "score": review["score"],
                    "evidence": review["evidence"],
                    "mistake_type": review["mistake_type"],
                }))
                return context, received, reference, review, profile

        context, received, reference, review, profile = anyio.run(scenario)

        assert received == {"received": True, "problem_id": "arrays_012"}
        assert reference["approach_tags"] == ["hashmap", "single_pass"]
        assert reference["locale"] == "tr"
        assert review["score"] == 0.5
        assert review["evidence"] == ["Correct approach described verbally, no code written"]
        assert review["mistake_type"] == "none"
        assert profile["topic_scores"]["arrays"] == pytest.approx(0.15)
        assert profile["recent_evidence"]["arrays"] == [
            "Correct approach described verbally, no code written"
        ]

    def test_mismatching_explanation_scores_lowest(self):
        context = build_context(":memory:")
        call_tool(context, "assess_level", {})
        call_tool(context, "explain_approach", {
            "problem_id": "arrays_012", "explanation": "Listeyi sıralayıp ortadan bakarım."
        })

        review = structured(call_tool(context, "review_solution", {
            "problem_id": "arrays_012",
            "attempt_type": "explanation",
            "reference_match": False,
        }))
        profile = structured(call_tool(context, "update_profile", {
            "topic": "arrays",
            "problem_id": "arrays_012",
            "score": review["score"],
            "evidence": review["evidence"],
            "mistake_type": review["mistake_type"],
        }))

        assert review["score"] == 0.2
        assert review["mistake_type"] == "wrong_approach"
        assert profile["topic_scores"]["arrays"] == pytest.approx(0.06)

    def test_explanation_text_is_never_persisted(self):
        context = build_context(":memory:")
        call_tool(context, "assess_level", {})
        secret = "bu metin hiçbir tabloya yazılmamalı"
        call_tool(context, "explain_approach", {
            "problem_id": "arrays_012", "explanation": secret
        })
        call_tool(context, "update_profile", {
            "topic": "arrays", "problem_id": "arrays_012", "score": 0.5,
            "evidence": ["Correct approach described verbally, no code written"],
        })

        dumped = "\n".join(context.connection.iterdump())
        assert secret not in dumped
