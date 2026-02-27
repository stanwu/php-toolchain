import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.models import Action, ActionPlan, ActionType, RiskLevel

logger = logging.getLogger(__name__)


class ConflictResolver:
    def __init__(self, plan: ActionPlan) -> None:
        self.plan = plan
        self._conflicts: list[dict[str, Any]] = []

    def resolve(self) -> ActionPlan:
        """
        Run all conflict checks in order and return a clean ActionPlan.
        Sets action.conflict = True on any action that was involved in a conflict.
        Logs each resolved conflict at WARNING level.
        """
        actions = self.plan.actions
        actions = self._find_delete_move_conflicts(actions)
        actions = self._find_duplicate_move_conflicts(actions)
        actions = self._find_redundant_deletes_in_gitignore_dirs(actions)
        actions = self._reorder_move_chain(actions)
        self.plan.actions = actions
        return self.plan

    def _find_delete_move_conflicts(self, actions: list[Action]) -> list[Action]:
        """Resolve DELETE+MOVE conflicts on the same source."""
        source_map = defaultdict(list)
        for action in actions:
            source_map[action.source].append(action)

        actions_to_remove = set()
        for source, group in source_map.items():
            if len(group) > 1:
                delete_action = next((a for a in group if a.action_type == ActionType.DELETE), None)
                move_action = next((a for a in group if a.action_type == ActionType.MOVE), None)

                if delete_action and move_action:
                    resolution = f"Removed DELETE, kept MOVE, and upgraded risk to HIGH for source '{source}'."
                    logger.warning(f"Conflict resolved: {resolution}")
                    self._conflicts.append({
                        "type": "DELETE+MOVE same source",
                        "source": source,
                        "resolution": resolution,
                        "actions_involved": [str(delete_action), str(move_action)],
                    })
                    actions_to_remove.add(delete_action)
                    move_action.conflict = True
                    move_action.risk_level = RiskLevel.HIGH
        
        return [a for a in actions if a not in actions_to_remove]

    def _find_duplicate_move_conflicts(self, actions: list[Action]) -> list[Action]:
        """Resolve two MOVEs on the same source."""
        source_map = defaultdict(list)
        for action in actions:
            if action.action_type == ActionType.MOVE:
                source_map[action.source].append(action)

        actions_to_remove = set()
        for source, group in source_map.items():
            if len(group) > 1:
                # Keep the first one, remove the rest
                first_action, rest = group[0], group[1:]
                first_action.conflict = True
                actions_to_remove.update(rest)
                
                resolution = f"Multiple MOVEs on source '{source}'. Kept first, removed {len(rest)} other(s)."
                logger.warning(f"Conflict resolved: {resolution}")
                self._conflicts.append({
                    "type": "Two MOVEs same source",
                    "source": source,
                    "resolution": resolution,
                    "actions_involved": [str(a) for a in group],
                })

        return [a for a in actions if a not in actions_to_remove]

    def _find_redundant_deletes_in_gitignore_dirs(self, actions: list[Action]) -> list[Action]:
        """
        If ADD_GITIGNORE action exists for dir X, remove any DELETE actions for files under X/.
        """
        gitignore_dirs = {
            Path(a.source) for a in actions if a.action_type == ActionType.ADD_GITIGNORE
        }
        if not gitignore_dirs:
            return actions

        actions_to_remove = set()
        delete_actions = [a for a in actions if a.action_type == ActionType.DELETE]

        for d_action in delete_actions:
            d_path = Path(d_action.source)
            for gi_dir in gitignore_dirs:
                # Check if the gitignore directory is one of the parents of the file to be deleted.
                if gi_dir in d_path.parents:
                    actions_to_remove.add(d_action)
                    resolution = f"Removed redundant DELETE on '{d_action.source}' because parent '{gi_dir}' is being added to .gitignore."
                    logger.warning(f"Conflict resolved: {resolution}")
                    self._conflicts.append({
                        "type": "DELETE after ADD_GITIGNORE on same dir",
                        "source": d_action.source,
                        "resolution": resolution,
                        "actions_involved": [str(d_action)],
                    })
                    break # Move to next delete action

        return [a for a in actions if a not in actions_to_remove]

    def _reorder_move_chain(self, actions: list[Action]) -> list[Action]:
        """Topological sort so move dependencies execute in correct order."""
        move_actions = [a for a in actions if a.action_type == ActionType.MOVE]
        other_actions = [a for a in actions if a.action_type != ActionType.MOVE]

        if not move_actions:
            return actions

        source_map = {a.source: a for a in move_actions}
        adj = defaultdict(list)
        in_degree = {a: 0 for a in move_actions}

        for move in move_actions:
            if move.destination and move.destination in source_map:
                # Dependency: source_map[move.destination] must run before move
                dependent = source_map[move.destination]
                adj[dependent].append(move)
                in_degree[move] += 1
                
                # Mark as conflict as they are chained
                if not move.conflict:
                    move.conflict = True
                if not dependent.conflict:
                    dependent.conflict = True
                
                resolution = f"Reordered chained MOVEs: '{dependent.source}->{dependent.destination}' must run before '{move.source}->{move.destination}'."
                self._conflicts.append({
                    "type": "MOVE target = another file's source",
                    "source": move.source,
                    "resolution": resolution,
                    "actions_involved": [str(dependent), str(move)],
                })


        # Kahn's algorithm for topological sort
        queue = [a for a in move_actions if in_degree[a] == 0]
        sorted_moves = []
        while queue:
            curr = queue.pop(0)
            sorted_moves.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_moves) != len(move_actions):
            logger.error("Cycle detected in MOVE actions; cannot determine safe order. Returning original move order.")
            # In case of cycle, return original order to avoid data loss
            return other_actions + move_actions

        return other_actions + sorted_moves

    def conflict_report(self) -> list[dict[str, Any]]:
        """
        Return list of {type, source, resolution, actions_involved}
        for every conflict that was detected (even if auto-resolved).
        """
        return self._conflicts
