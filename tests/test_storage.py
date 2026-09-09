import json

import pytest

from src.storage import sqlite as db


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


class TestSchema:
    def test_tables_from_the_schema_doc_exist(self, conn):
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        names = {row["name"] for row in rows}

        assert {"profile", "topic_scores", "recent_errors", "attempts"} <= names

    def test_init_is_idempotent(self, conn):
        db.init_db(conn)
        db.init_db(conn)
        assert db.get_profile(conn) is None

    def test_profile_table_holds_a_single_row(self, conn):
        db.create_profile(conn, level="beginner", preferred_language="tr")

        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO profile (id, level, preferred_language, created_at, updated_at) "
                "VALUES (2, 'beginner', 'tr', 'now', 'now')"
            )

    def test_creating_a_second_profile_is_rejected(self, conn):
        db.create_profile(conn, level="beginner", preferred_language="tr")
        with pytest.raises(ValueError, match="already exists"):
            db.create_profile(conn, level="beginner", preferred_language="en")

    def test_file_backed_database_persists_across_connections(self, tmp_path):
        path = tmp_path / "profile.db"
        first = db.connect(path)
        db.create_profile(first, level="beginner", preferred_language="tr")
        db.set_topic_score(first, "arrays", 0.42)
        first.close()

        second = db.connect(path)
        assert db.get_topic_scores(second) == {"arrays": 0.42}
        assert db.get_profile(second)["preferred_language"] == "tr"
        second.close()


class TestProfileRow:
    def test_profile_exists_reflects_state(self, conn):
        assert db.profile_exists(conn) is False
        db.create_profile(conn, level="beginner", preferred_language="tr")
        assert db.profile_exists(conn) is True

    def test_created_and_updated_at_are_set(self, conn):
        db.create_profile(conn, level="beginner", preferred_language="tr")
        profile = db.get_profile(conn)

        assert profile["created_at"] == profile["updated_at"]
        assert profile["created_at"].endswith("+00:00")

    def test_partial_update_leaves_other_columns_alone(self, conn):
        db.create_profile(
            conn, level="beginner", preferred_language="tr", current_focus="arrays"
        )
        db.update_profile_row(conn, level="intermediate")
        profile = db.get_profile(conn)

        assert profile["level"] == "intermediate"
        assert profile["current_focus"] == "arrays"
        assert profile["preferred_language"] == "tr"
        assert profile["updated_at"] >= profile["created_at"]

    def test_updating_without_a_profile_raises(self, conn):
        with pytest.raises(LookupError):
            db.update_profile_row(conn, level="advanced")


class TestTopicScores:
    def test_seed_replaces_the_whole_table(self, conn):
        db.seed_topic_scores(conn, {"arrays": 0.0, "graphs": 0.0})
        db.set_topic_score(conn, "arrays", 0.5)
        db.seed_topic_scores(conn, {"arrays": 0.0, "dp": 0.0})

        assert db.get_topic_scores(conn) == {"arrays": 0.0, "dp": 0.0}

    def test_set_topic_score_upserts(self, conn):
        db.set_topic_score(conn, "arrays", 0.3)
        db.set_topic_score(conn, "arrays", 0.6)

        assert db.get_topic_score(conn, "arrays") == 0.6

    def test_unknown_topic_reads_as_none(self, conn):
        assert db.get_topic_score(conn, "graphs") is None


class TestRecentErrors:
    def test_entries_are_pruned_to_three_per_topic(self, conn):
        for index in range(6):
            db.add_recent_errors(conn, "arrays", [f"hata {index}"])

        stored = db.get_recent_errors(conn)["arrays"]
        assert stored == ["hata 5", "hata 4", "hata 3"]

    def test_a_single_call_with_many_entries_is_also_pruned(self, conn):
        db.add_recent_errors(conn, "arrays", ["bir", "iki", "üç", "dört"])

        rows = conn.execute("SELECT COUNT(*) AS total FROM recent_errors").fetchone()
        assert rows["total"] == 3

    def test_topics_are_pruned_independently(self, conn):
        for index in range(4):
            db.add_recent_errors(conn, "arrays", [f"a{index}"])
        db.add_recent_errors(conn, "graphs", ["g0"])

        errors = db.get_recent_errors(conn)
        assert len(errors["arrays"]) == 3
        assert errors["graphs"] == ["g0"]

    def test_clear_removes_everything(self, conn):
        db.add_recent_errors(conn, "arrays", ["hata"])
        db.clear_recent_errors(conn)

        assert db.get_recent_errors(conn) == {}


class TestAttempts:
    def test_attempt_round_trips_with_json_evidence(self, conn):
        db.insert_attempt(
            conn,
            problem_id="arrays_012",
            topic="arrays",
            score=0.8,
            evidence=["Correct algorithm, needed one hint"],
            hints_used=1,
            mistake_type=None,
        )
        attempt = db.get_attempts(conn)[0]

        assert attempt["problem_id"] == "arrays_012"
        assert attempt["score"] == 0.8
        assert attempt["evidence"] == ["Correct algorithm, needed one hint"]
        assert attempt["hints_used"] == 1
        assert attempt["mistake_type"] is None

    def test_evidence_is_stored_as_json_text(self, conn):
        db.insert_attempt(
            conn,
            problem_id="p",
            topic="arrays",
            score=0.2,
            evidence=["a", "b"],
            hints_used=0,
            mistake_type="wrong_approach",
        )
        raw = conn.execute("SELECT evidence FROM attempts").fetchone()["evidence"]

        assert json.loads(raw) == ["a", "b"]

    def test_history_is_never_pruned(self, conn):
        for index in range(10):
            db.insert_attempt(
                conn,
                problem_id=f"p{index}",
                topic="arrays",
                score=0.2,
                evidence=[],
                hints_used=0,
                mistake_type=None,
            )
        assert len(db.get_attempts(conn)) == 10

    def test_attempts_come_back_newest_first(self, conn):
        for index in range(3):
            db.insert_attempt(
                conn,
                problem_id=f"p{index}",
                topic="arrays",
                score=0.2,
                evidence=[],
                hints_used=0,
                mistake_type=None,
            )
        assert [a["problem_id"] for a in db.get_attempts(conn)] == ["p2", "p1", "p0"]

    def test_filtering_and_limiting(self, conn):
        for topic in ("arrays", "graphs", "arrays"):
            db.insert_attempt(
                conn,
                problem_id="p",
                topic=topic,
                score=0.2,
                evidence=[],
                hints_used=0,
                mistake_type=None,
            )
        assert len(db.get_attempts(conn, topic="arrays")) == 2
        assert len(db.get_attempts(conn, limit=1)) == 1
