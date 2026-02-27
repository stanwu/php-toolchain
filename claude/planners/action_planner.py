import logging
from datetime import datetime, timezone

from core.models import Action, ActionPlan, ActionType, AnalysisResult, RiskLevel

logger = logging.getLogger(__name__)

RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}

TYPE_ORDER = {
    ActionType.ADD_GITIGNORE: 0,
    ActionType.DELETE: 1,
    ActionType.MOVE: 2,
    ActionType.REPORT_ONLY: 3,
}


class ActionPlanner:
    def __init__(self, results: list[AnalysisResult], project_dir: str) -> None:
        self._results = results
        self._project_dir = project_dir

    def build_plan(self) -> ActionPlan:
        all_actions: list[Action] = []
        for result in self._results:
            all_actions.extend(result.actions)

        deduped = self._deduplicate(all_actions)
        sorted_actions = sorted(deduped, key=self._sort_key)

        return ActionPlan(
            actions=sorted_actions,
            created_at=datetime.now(timezone.utc).isoformat(),
            project_dir=self._project_dir,
        )

    def _deduplicate(self, actions: list[Action]) -> list[Action]:
        best: dict[tuple, Action] = {}
        for action in actions:
            key = (action.action_type, action.source)
            if key not in best:
                best[key] = action
            else:
                existing = best[key]
                if RISK_ORDER[action.risk_level] < RISK_ORDER[existing.risk_level]:
                    best[key] = action
        return list(best.values())

    def _sort_key(self, action: Action) -> tuple:
        return (
            RISK_ORDER[action.risk_level],
            TYPE_ORDER[action.action_type],
            action.source,
        )

    def summary(self, plan: ActionPlan) -> dict:
        by_risk: dict[str, int] = {
            RiskLevel.LOW.value: 0,
            RiskLevel.MEDIUM.value: 0,
            RiskLevel.HIGH.value: 0,
        }
        by_type: dict[str, int] = {
            ActionType.ADD_GITIGNORE.value: 0,
            ActionType.DELETE.value: 0,
            ActionType.MOVE.value: 0,
            ActionType.REPORT_ONLY.value: 0,
        }

        for action in plan.actions:
            by_risk[action.risk_level.value] += 1
            by_type[action.action_type.value] += 1

        return {
            "total": len(plan.actions),
            "by_risk": by_risk,
            "by_type": by_type,
        }
