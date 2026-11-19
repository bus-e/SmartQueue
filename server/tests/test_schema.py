"""Схема базы и доменная модель должны говорить на одном языке."""

import re
from pathlib import Path

from app.domain.model import (
    EntryStatus,
    NoticeType,
    NotifyThreshold,
    QueueCode,
    QueueStatus,
    QueueType,
    Role,
    Source,
)

path = Path(__file__).parent.parent / "migrations" / "versions" / "0001_init.py"
SQL = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def check_values(column: str) -> set[str]:
    m = re.search(rf"CHECK \({column} IN \(([^)]*)\)\)", SQL)
    assert m, f"нет ограничения для {column}"
    return set(re.findall(r"'(\w+)'", m.group(1)))


def test_types_sources_roles_match_domain():
    m = re.search(r"CHECK \(type IN \('regular'[^)]*\)\)", SQL)
    assert set(re.findall(r"'(\w+)'", m.group(0))) == {t.value for t in QueueType}
    m = re.search(r"CHECK \(status IN \('open'[^)]*\)\)", SQL)
    assert set(re.findall(r"'(\w+)'", m.group(0))) == {s.value for s in QueueStatus}
    assert check_values("source") == {s.value for s in Source}
    assert check_values("role") == {r.value for r in Role}


def test_member_statuses_match_domain():
    m = re.search(r"CHECK \(status IN \('waiting'[^)]*\)\)", SQL)
    assert set(re.findall(r"'(\w+)'", m.group(0))) == {s.value for s in EntryStatus}


def test_notice_types_match_domain():
    m = re.search(r"CHECK \(type IN \('n_ahead'[^)]*\)\)", SQL)
    assert set(re.findall(r"'(\w+)'", m.group(0))) == {t.value for t in NoticeType}


def test_code_rule_matches_domain():
    pattern = re.search(r"code ~ '([^']+)'", SQL).group(1)
    assert re.fullmatch(pattern, "K7M2QX")
    for bad in ["K0M2QX", "KOM2QX", "K1M2QX", "KIM2QX", "K7M2Q"]:
        assert not re.fullmatch(pattern, bad)
    assert all(re.fullmatch(pattern, QueueCode.generate().value) for _ in range(100))


def test_threshold_default_and_range():
    assert "notify_before smallint NOT NULL DEFAULT 2 CHECK (notify_before BETWEEN 1 AND 10)" in SQL
    assert NotifyThreshold().value == 2


def test_seven_tables():
    assert len(re.findall(r"CREATE TABLE", SQL)) == 7
