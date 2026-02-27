from __future__ import annotations

from datetime import datetime, timezone

from core.models import Action, ActionPlan, ActionType, AnalysisResult, RiskLevel

RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}

ACTION_TYPE_ORDER = {
    ActionType.ADD_GITIGNORE: 0,
    ActionType.DELETE: 1,
    ActionType.MOVE: 2,
    ActionType.REPORT_ONLY: 3,
}


class ActionPlanner:
    def __init__(self, results: list[AnalysisResult], project_dir: str) -> None:
        self._results = list(results)
        self._project_dir = project_dir

    def build_plan(self) -> ActionPlan:
        actions: list[Action] = []
        for result in self._results:
            actions.extend(result.actions)

        actions = self._deduplicate(actions)
        actions.sort(key=self._sort_key)

        created_at = datetime.now(timezone.utc).isoformat()
        return ActionPlan(actions=actions, created_at=created_at, project_dir=self._project_dir)

    def _deduplicate(self, actions: list[Action]) -> list[Action]:
        best: dict[tuple[ActionType, str], Action] = {}
        for action in actions:
            key = (action.action_type, action.source)
            existing = best.get(key)
            if existing is None:
                best[key] = action
                continue
            if RISK_ORDER[action.risk_level] < RISK_ORDER[existing.risk_level]:
                best[key] = action
        return list(best.values())

    def _sort_key(self, action: Action) -> tuple[int, int, str]:
        return (
            RISK_ORDER.get(action.risk_level, 99),
            ACTION_TYPE_ORDER.get(action.action_type, 99),
            action.source,
        )

    def summary(self, plan: ActionPlan) -> dict:
        by_risk: dict[str, int] = {level.value: 0 for level in RiskLevel}
        by_type: dict[str, int] = {atype.value: 0 for atype in ActionType}

        for action in plan.actions:
            by_risk[action.risk_level.value] = by_risk.get(action.risk_level.value, 0) + 1
            by_type[action.action_type.value] = by_type.get(action.action_type.value, 0) + 1

        return {
            "total": len(plan.actions),
            "by_risk": by_risk,
            "by_type": by_type,
        }

