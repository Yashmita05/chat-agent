import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import Memory  # noqa: E402


def make(tmp_path, session="s", tz="Asia/Kolkata"):
    return Memory(str(tmp_path / "m.db"), session, tz)


def test_recent_messages_start_with_user(tmp_path):
    m = make(tmp_path)
    m.add("user", "q1")
    m.add("assistant", "a1")
    m.add("user", "q2")
    m.add("assistant", "a2")
    msgs = m.recent_messages(3)  # window cuts mid-pair
    assert msgs[0]["role"] == "user"
    assert [x["content"] for x in msgs] == ["q2", "a2"]


def test_question_log_has_local_timestamps_and_only_questions(tmp_path):
    m = make(tmp_path)
    # 2026-11-10 12:00 UTC == 17:30 IST
    ts = 1794312000.0
    m.add("user", "who won the match?", ts=ts)
    m.add("assistant", "India did.", ts=ts + 1)
    log = m.question_log()
    assert "who won the match?" in log
    assert "India did." not in log
    assert log.startswith("[2026-11-10 17:30]")


def test_long_questions_are_truncated(tmp_path):
    m = make(tmp_path)
    m.add("user", "x" * 500)
    line = m.question_log(max_chars=50)
    assert line.endswith("…")
    assert len(line.split("] ", 1)[1]) == 50


def test_sessions_are_isolated_and_persist(tmp_path):
    a = make(tmp_path, "a")
    b = make(tmp_path, "b")
    a.add("user", "only a")
    assert b.question_log() == ""
    a2 = make(tmp_path, "a")  # reopen db: memory survives restart
    assert "only a" in a2.question_log()


def test_clear(tmp_path):
    m = make(tmp_path)
    m.add("user", "hi")
    m.clear()
    assert m.recent_messages() == []
