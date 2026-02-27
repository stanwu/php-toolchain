from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.models import Action, ActionPlan, ActionType, RiskLevel
from main import _filter_plan_by_risk, _load_plan, _risk_ceiling, _write_json


def test_risk_ceiling_parses_valid_levels() -> None:
    assert _risk_ceiling("LOW") == RiskLevel.LOW
    assert _risk_ceiling("MEDIUM") == RiskLevel.MEDIUM
    assert _risk_ceiling("HIGH") == RiskLevel.HIGH


def test_risk_ceiling_rejects_invalid_level() -> None:
    with pytest.raises(ValueError):
        _risk_ceiling("NOPE")


def test_filter_plan_by_risk_returns_same_plan_for_high() -> None:
    plan = ActionPlan(actions=[], created_at="t", project_dir="p")
    out = _filter_plan_by_risk(plan, RiskLevel.HIGH)
    assert out is plan


def test_filter_plan_by_risk_filters_actions() -> None:
    actions = [
        Action(ActionType.REPORT_ONLY, "a", None, RiskLevel.LOW, "r"),
        Action(ActionType.REPORT_ONLY, "b", None, RiskLevel.MEDIUM, "r"),
        Action(ActionType.REPORT_ONLY, "c", None, RiskLevel.HIGH, "r"),
    ]
    plan = ActionPlan(actions=actions, created_at="t", project_dir="p")
    out = _filter_plan_by_risk(plan, RiskLevel.MEDIUM)
    assert [a.source for a in out.actions] == ["a", "b"]


def test_write_json_creates_parent_dirs_and_newline(tmp_path: Path) -> None:
    p = tmp_path / "a" / "b" / "out.json"
    _write_json(p, {"b": 2, "a": 1})
    raw = p.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert json.loads(raw) == {"a": 1, "b": 2}


def test_load_plan_requires_object_root(tmp_path: Path) -> None:
    p = tmp_path / "plan.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        _load_plan(p)
