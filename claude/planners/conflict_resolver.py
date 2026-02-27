import logging
from collections import defaultdict, deque

from core.models import Action, ActionPlan, ActionType, RiskLevel

logger = logging.getLogger(__name__)


class ConflictResolver:
    def __init__(self, plan: ActionPlan) -> None:
        self._plan = plan
        self._conflicts: list[dict] = []

    def resolve(self) -> ActionPlan:
        """
        Run all conflict checks in order and return a clean ActionPlan.
        Sets action.conflict = True on any action that was involved in a conflict.
        Logs each resolved conflict at WARNING level.
        """
        actions = list(self._plan.actions)
        actions = self._find_delete_move_conflicts(actions)
        actions = self._find_duplicate_move_conflicts(actions)
        actions = self._find_redundant_deletes_in_gitignore_dirs(actions)
        actions = self._reorder_move_chain(actions)
        return ActionPlan(
            actions=actions,
            created_at=self._plan.created_at,
            project_dir=self._plan.project_dir,
        )

    def _find_delete_move_conflicts(
        self, actions: list[Action]
    ) -> list[Action]:
        """Resolve DELETE+MOVE conflicts on the same source."""
        by_source: dict[str, list[Action]] = defaultdict(list)
        for action in actions:
            by_source[action.source].append(action)

        to_remove: set[int] = set()
        for source, acts in by_source.items():
            deletes = [a for a in acts if a.action_type == ActionType.DELETE]
            moves = [a for a in acts if a.action_type == ActionType.MOVE]

            if deletes and moves:
                for delete in deletes:
                    to_remove.add(id(delete))
                for move in moves:
                    move.conflict = True
                    move.risk_level = RiskLevel.HIGH
                self._conflicts.append({
                    "type": "DELETE_MOVE_CONFLICT",
                    "source": source,
                    "resolution": "DELETE removed, MOVE kept with HIGH risk",
                    "actions_involved": deletes + moves,
                })
                logger.warning(
                    "DELETE+MOVE conflict on %s: removed DELETE, kept MOVE at HIGH risk",
                    source,
                )

        return [a for a in actions if id(a) not in to_remove]

    def _find_duplicate_move_conflicts(
        self, actions: list[Action]
    ) -> list[Action]:
        """Resolve two MOVEs on the same source."""
        seen: dict[str, Action] = {}
        to_remove: set[int] = set()

        for action in actions:
            if action.action_type == ActionType.MOVE:
                if action.source in seen:
                    to_remove.add(id(action))
                    first = seen[action.source]
                    self._conflicts.append({
                        "type": "DUPLICATE_MOVE_CONFLICT",
                        "source": action.source,
                        "resolution": "First MOVE kept, duplicate removed",
                        "actions_involved": [first, action],
                    })
                    logger.warning(
                        "Duplicate MOVE for %s: keeping first (dest=%s), dropping second (dest=%s)",
                        action.source,
                        first.destination,
                        action.destination,
                    )
                else:
                    seen[action.source] = action

        return [a for a in actions if id(a) not in to_remove]

    def _find_redundant_deletes_in_gitignore_dirs(
        self, actions: list[Action]
    ) -> list[Action]:
        """
        If ADD_GITIGNORE action exists for dir X,
        remove any DELETE actions for files under X/.
        """
        gitignore_actions = [
            a for a in actions if a.action_type == ActionType.ADD_GITIGNORE
        ]
        if not gitignore_actions:
            return actions

        # Normalise: strip trailing slashes for consistent prefix matching
        gitignore_dirs = [(a, a.source.rstrip("/")) for a in gitignore_actions]

        to_remove: set[int] = set()
        for action in actions:
            if action.action_type == ActionType.DELETE:
                for gi_action, gi_dir in gitignore_dirs:
                    if action.source.startswith(gi_dir + "/"):
                        to_remove.add(id(action))
                        self._conflicts.append({
                            "type": "REDUNDANT_DELETE",
                            "source": action.source,
                            "resolution": (
                                f"DELETE removed, covered by ADD_GITIGNORE for {gi_dir}"
                            ),
                            "actions_involved": [gi_action, action],
                        })
                        logger.warning(
                            "Redundant DELETE %s: covered by ADD_GITIGNORE for %s",
                            action.source,
                            gi_dir,
                        )
                        break  # one matching gitignore dir is enough

        return [a for a in actions if id(a) not in to_remove]

    def _reorder_move_chain(
        self, actions: list[Action]
    ) -> list[Action]:
        """Topological sort so move dependencies execute in correct order.

        If A→B and B→C both exist, B→C must run first so A doesn't overwrite B.
        """
        non_moves = [a for a in actions if a.action_type != ActionType.MOVE]
        moves = [a for a in actions if a.action_type == ActionType.MOVE]

        if not moves:
            return non_moves

        # source path → the MOVE action that starts from that path
        source_to_move: dict[str, Action] = {a.source: a for a in moves}

        # successors[id(X)] = actions that must execute AFTER X
        successors: dict[int, list[Action]] = defaultdict(list)
        in_degree: dict[int, int] = {id(a): 0 for a in moves}

        for action in moves:
            if action.destination and action.destination in source_to_move:
                # action.destination is also the source of another move;
                # that other move must complete first.
                other = source_to_move[action.destination]
                successors[id(other)].append(action)
                in_degree[id(action)] += 1

        queue: deque[Action] = deque(a for a in moves if in_degree[id(a)] == 0)
        sorted_moves: list[Action] = []

        while queue:
            action = queue.popleft()
            sorted_moves.append(action)
            for successor in successors[id(action)]:
                in_degree[id(successor)] -= 1
                if in_degree[id(successor)] == 0:
                    queue.append(successor)

        # Append any remaining (e.g., cycles — defensive)
        seen_ids = {id(a) for a in sorted_moves}
        sorted_moves.extend(a for a in moves if id(a) not in seen_ids)

        return non_moves + sorted_moves

    def conflict_report(self) -> list[dict]:
        """
        Return list of {type, source, resolution, actions_involved}
        for every conflict that was detected (even if auto-resolved).
        """
        return list(self._conflicts)
