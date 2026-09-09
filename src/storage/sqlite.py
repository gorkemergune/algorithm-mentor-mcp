"""SQLite erişim katmanı — şema `docs/STUDENT_PROFILE_SCHEMA.md` → "Depolama".

Tek kullanıcılı yerel kurulum: `profile` tablosu tek satırdır (`id = 1`),
bu yüzden `user_id` kolonu yoktur. Bu modül yalnızca veri okur/yazar; hiçbir
iş kuralı (skor, seviye, budama eşiği) burada karar verilmez — onlar
`src/domain` ve tool katmanına aittir.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "profile.db"

#: `recent_evidence` tablosunda konu başına saklanan en fazla satır.
RECENT_EVIDENCE_PER_TOPIC = 3

PROFILE_ROW_ID = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  level TEXT NOT NULL,
  current_focus TEXT,
  preferred_language TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_scores (
  topic TEXT PRIMARY KEY,
  score REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS recent_evidence (
  topic TEXT NOT NULL,
  evidence TEXT NOT NULL,
  timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  problem_id TEXT NOT NULL,
  topic TEXT NOT NULL,
  score REAL NOT NULL,
  evidence TEXT NOT NULL,
  hints_used INTEGER NOT NULL,
  mistake_type TEXT,
  timestamp TEXT NOT NULL
);
"""


def utc_now() -> str:
    """Tabloların `TEXT` zaman damgası formatı: ISO-8601, UTC."""
    return datetime.now(timezone.utc).isoformat()


# --- bağlantı ---------------------------------------------------------------


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Bağlantı açar ve şemayı kurar (idempotent)."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    init_db(connection)
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    """Tabloları oluşturur; varsa dokunmaz. Eski isimli tabloyu düşürür."""
    with connection:
        # `recent_errors` → `recent_evidence` yeniden adlandırması: alan hem
        # başarı hem başarısızlık kanıtı tutuyor. Production verisi olmadığı
        # için eski tablo taşınmadan düşürülür.
        connection.execute("DROP TABLE IF EXISTS recent_errors")
        connection.executescript(SCHEMA)


# --- profile ----------------------------------------------------------------


def profile_exists(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT 1 FROM profile WHERE id = ?", (PROFILE_ROW_ID,)).fetchone()
    return row is not None


def create_profile(
    connection: sqlite3.Connection,
    *,
    level: str,
    preferred_language: str,
    current_focus: str | None = None,
) -> None:
    """Tek satırlık profili oluşturur. Zaten varsa `ValueError`."""
    if profile_exists(connection):
        raise ValueError("profile already exists (use update_profile_row / retake)")
    now = utc_now()
    with connection:
        connection.execute(
            "INSERT INTO profile (id, level, current_focus, preferred_language, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (PROFILE_ROW_ID, level, current_focus, preferred_language, now, now),
        )


def get_profile(connection: sqlite3.Connection) -> dict | None:
    row = connection.execute(
        "SELECT level, current_focus, preferred_language, created_at, updated_at "
        "FROM profile WHERE id = ?",
        (PROFILE_ROW_ID,),
    ).fetchone()
    return dict(row) if row is not None else None


def update_profile_row(
    connection: sqlite3.Connection,
    *,
    level: str | None = None,
    current_focus: str | None = None,
    preferred_language: str | None = None,
) -> None:
    """Verilen alanları günceller; `updated_at` her çağrıda tazelenir."""
    if not profile_exists(connection):
        raise LookupError("no profile row to update")

    updates = {
        "level": level,
        "current_focus": current_focus,
        "preferred_language": preferred_language,
    }
    assignments = [f"{column} = ?" for column, value in updates.items() if value is not None]
    values = [value for value in updates.values() if value is not None]
    assignments.append("updated_at = ?")
    values.append(utc_now())

    with connection:
        connection.execute(
            f"UPDATE profile SET {', '.join(assignments)} WHERE id = ?",
            (*values, PROFILE_ROW_ID),
        )


# --- topic_scores -----------------------------------------------------------


def get_topic_scores(connection: sqlite3.Connection) -> dict[str, float]:
    rows = connection.execute("SELECT topic, score FROM topic_scores ORDER BY topic").fetchall()
    return {row["topic"]: row["score"] for row in rows}


def get_topic_score(connection: sqlite3.Connection, topic: str) -> float | None:
    """Konunun skoru; satır yoksa `None` (yani `assess_level` seed'lememiş)."""
    row = connection.execute(
        "SELECT score FROM topic_scores WHERE topic = ?", (topic,)
    ).fetchone()
    return row["score"] if row is not None else None


def set_topic_score(connection: sqlite3.Connection, topic: str, score: float) -> None:
    with connection:
        connection.execute(
            "INSERT INTO topic_scores (topic, score) VALUES (?, ?) "
            "ON CONFLICT(topic) DO UPDATE SET score = excluded.score",
            (topic, score),
        )


def seed_topic_scores(connection: sqlite3.Connection, scores: dict[str, float]) -> None:
    """`topic_scores` tablosunu verilen sözlükle baştan kurar."""
    with connection:
        connection.execute("DELETE FROM topic_scores")
        connection.executemany(
            "INSERT INTO topic_scores (topic, score) VALUES (?, ?)",
            list(scores.items()),
        )


# --- recent_evidence --------------------------------------------------------


def add_recent_evidence(
    connection: sqlite3.Connection,
    topic: str,
    evidence: list[str],
    *,
    keep: int = RECENT_EVIDENCE_PER_TOPIC,
) -> None:
    """Evidence girdilerini ekler ve konuyu `keep` satıra budar."""
    timestamp = utc_now()
    with connection:
        connection.executemany(
            "INSERT INTO recent_evidence (topic, evidence, timestamp) VALUES (?, ?, ?)",
            [(topic, entry, timestamp) for entry in evidence],
        )
        # Aynı saniyede eklenen satırlar için rowid ikinci sıralama anahtarı.
        connection.execute(
            "DELETE FROM recent_evidence WHERE topic = ? AND rowid NOT IN ("
            "  SELECT rowid FROM recent_evidence WHERE topic = ? "
            "  ORDER BY timestamp DESC, rowid DESC LIMIT ?"
            ")",
            (topic, topic, keep),
        )


def get_recent_evidence(
    connection: sqlite3.Connection,
    *,
    keep: int = RECENT_EVIDENCE_PER_TOPIC,
) -> dict[str, list[str]]:
    """Konu → en yeni `keep` evidence girdisi (yeniden eskiye)."""
    rows = connection.execute(
        "SELECT topic, evidence FROM recent_evidence ORDER BY topic, timestamp DESC, rowid DESC"
    ).fetchall()
    grouped: dict[str, list[str]] = {}
    for row in rows:
        entries = grouped.setdefault(row["topic"], [])
        if len(entries) < keep:
            entries.append(row["evidence"])
    return grouped


def clear_recent_evidence(connection: sqlite3.Connection) -> None:
    with connection:
        connection.execute("DELETE FROM recent_evidence")


# --- attempts ---------------------------------------------------------------


def insert_attempt(
    connection: sqlite3.Connection,
    *,
    problem_id: str,
    topic: str,
    score: float,
    evidence: list[str],
    hints_used: int,
    mistake_type: str | None,
) -> None:
    """Denemeyi kalıcı geçmişe yazar — `attempts` asla budanmaz."""
    with connection:
        connection.execute(
            "INSERT INTO attempts (problem_id, topic, score, evidence, hints_used, "
            "mistake_type, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                problem_id,
                topic,
                score,
                json.dumps(evidence, ensure_ascii=False),
                hints_used,
                mistake_type,
                utc_now(),
            ),
        )


def get_attempts(
    connection: sqlite3.Connection,
    *,
    topic: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Denemeleri en yeniden eskiye döner; `evidence` listeye çözülür."""
    query = "SELECT * FROM attempts"
    params: list = []
    if topic is not None:
        query += " WHERE topic = ?"
        params.append(topic)
    query += " ORDER BY id DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    rows = connection.execute(query, params).fetchall()
    attempts = []
    for row in rows:
        attempt = dict(row)
        attempt["evidence"] = json.loads(attempt["evidence"])
        attempts.append(attempt)
    return attempts
