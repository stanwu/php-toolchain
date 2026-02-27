from datetime import datetime, timezone
from collections import Counter
from typing import List, Dict

from core.models import AnalysisResult, ActionPlan, Action, RiskLevel, ActionType

RISK_ORDER: Dict[RiskLevel, int] = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
ACTION_TYPE_ORDER: Dict[ActionType, int] = {
    ActionType.ADD_GITIGNORE: 0,
    ActionType.DELETE: 1,
    ActionType.MOVE: 2,
    ActionType.REPORT_ONLY: 3,
}

class ActionPlanner:
    def __init__(
        self,
        results: List[AnalysisResult],
        project_dir: str
    ) -> None:
        self.results = results
        self.project_dir = project_dir

    def build_plan(self) -> ActionPlan:
        """
        1. Collect all actions from all AnalysisResults.
        2. Deduplicate: if two actions have the same (action_type, source),
           keep the one with the LOWER risk level (more conservative).
        3. Sort: PRIMARY by risk level ascending (LOW first),
                 SECONDARY by action_type (ADD_GITIGNORE → DELETE → MOVE → REPORT_ONLY),
                 TERTIARY by source path alphabetically.
        4. Set ActionPlan.created_at = ISO 8601 UTC timestamp.
        5. Set ActionPlan.project_dir = project_dir.
        6. Return the ActionPlan.
        """
        all_actions: List[Action] = [action for result in self.results for action in result.actions]
        
        deduplicated_actions = self._deduplicate(all_actions)
        
        sorted_actions = sorted(deduplicated_actions, key=self._sort_key)
        
        plan = ActionPlan(
            actions=sorted_actions,
            created_at=datetime.now(timezone.utc).isoformat(),
            project_dir=self.project_dir
        )
        
        return plan

    def _deduplicate(self, actions: List[Action]) -> List[Action]:
        """Remove duplicate (action_type, source) pairs, keeping lowest risk."""
        unique_actions: Dict[tuple[ActionType, str], Action] = {}
        for action in actions:
            key = (action.action_type, action.source)
            if key not in unique_actions or RISK_ORDER[action.risk_level] < RISK_ORDER[unique_actions[key].risk_level]:
                unique_actions[key] = action
        return list(unique_actions.values())

    def _sort_key(self, action: Action) -> tuple:
        """Return a tuple used for sorting."""
        return (
            RISK_ORDER[action.risk_level],
            ACTION_TYPE_ORDER[action.action_type],
            action.source
        )

    def summary(self, plan: ActionPlan) -> dict:
        """
        Return a summary dict:
        {
          "total": N,
          "by_risk": {"LOW": N, "MEDIUM": N, "HIGH": N},
          "by_type": {"DELETE": N, "ADD_GITIGNORE": N, ...}
        }
        """
        total = len(plan.actions)
        by_risk = Counter(action.risk_level.name for action in plan.actions)
        by_type = Counter(action.action_type.name for action in plan.actions)
        
        # Ensure all keys exist, even if count is 0
        summary_by_risk = {level.name: by_risk.get(level.name, 0) for level in RiskLevel}
        summary_by_type = {atype.name: by_type.get(atype.name, 0) for atype in ActionType}

        return {
            "total": total,
            "by_risk": summary_by_risk,
            "by_type": summary_by_type,
        }
