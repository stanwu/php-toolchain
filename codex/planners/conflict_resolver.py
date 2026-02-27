from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any

from core.models import Action, ActionPlan, ActionType, RiskLevel

logger = logging.getLogger(__name__)


def _normalize_dir(dir_path: str) -> str:
    p = dir_path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


class ConflictResolver:
    def __init__(self, plan: ActionPlan) -> None:
        self._plan = plan
        self._conflicts: list[dict[str, Any]] = []

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

    def _record(
        self,
        *,
        conflict_type: str,
        source: str,
        resolution: str,
        actions_involved: list[Action],
    ) -> None:
        self._conflicts.append(
            {
                "type": conflict_type,
                "source": source,
                "resolution": resolution,
                "actions_involved": [a.to_dict() for a in actions_involved],
            }
        )

    def _find_delete_move_conflicts(self, actions: list[Action]) -> list[Action]:
        """Resolve DELETE+MOVE conflicts on the same source."""
        has_move: set[str] = {a.source for a in actions if a.action_type == ActionType.MOVE}
        if not has_move:
            return actions

        filtered: list[Action] = []
        for action in actions:
            if action.action_type == ActionType.DELETE and action.source in has_move:
                moves = [
                    a for a in actions if a.action_type == ActionType.MOVE and a.source == action.source
                ]
                for move in moves:
                    move.conflict = True
                    if move.risk_level < RiskLevel.HIGH:
                        move.risk_level = RiskLevel.HIGH

                logger.warning(
                    "Conflict DELETE+MOVE on %s: removed DELETE, kept MOVE",
                    action.source,
                )
                self._record(
                    conflict_type="DELETE_MOVE_SAME_SOURCE",
                    source=action.source,
                    resolution="removed DELETE; kept MOVE; marked MOVE conflict and upgraded to HIGH",
                    actions_involved=[action, *moves],
                )
                continue

            filtered.append(action)

        return filtered

    def _find_duplicate_move_conflicts(self, actions: list[Action]) -> list[Action]:
        """Resolve two MOVEs on the same source."""
        moves_by_source: dict[str, list[tuple[int, Action]]] = defaultdict(list)
        for idx, action in enumerate(actions):
            if action.action_type == ActionType.MOVE:
                moves_by_source[action.source].append((idx, action))

        if not moves_by_source:
            return actions

        to_remove: set[int] = set()
        for source, indexed_moves in moves_by_source.items():
            if len(indexed_moves) <= 1:
                continue

            # Prefer lowest risk; tie-breaker: earliest in plan.
            indexed_moves_sorted = sorted(indexed_moves, key=lambda t: (t[1].risk_level, t[0]))
            keep_idx, keep_action = indexed_moves_sorted[0]
            involved = [a for _, a in indexed_moves]

            keep_action.conflict = True
            for idx, _action in indexed_moves:
                if idx != keep_idx:
                    to_remove.add(idx)

            logger.warning(
                "Conflict MOVE+MOVE on %s: kept %s, removed %d other MOVE(s)",
                source,
                keep_action.destination,
                len(indexed_moves) - 1,
            )
            self._record(
                conflict_type="DUPLICATE_MOVE_SAME_SOURCE",
                source=source,
                resolution="kept lowest-risk MOVE; removed other MOVE(s); marked kept MOVE conflict",
                actions_involved=involved,
            )

        if not to_remove:
            return actions

        return [a for i, a in enumerate(actions) if i not in to_remove]

    def _find_redundant_deletes_in_gitignore_dirs(self, actions: list[Action]) -> list[Action]:
        """
        If ADD_GITIGNORE action exists for dir X,
        remove any DELETE actions for files under X/.
        """
        gitignore_dirs = [_normalize_dir(a.source) for a in actions if a.action_type == ActionType.ADD_GITIGNORE]
        gitignore_dirs = [d for d in gitignore_dirs if d]
        if not gitignore_dirs:
            return actions

        filtered: list[Action] = []
        for action in actions:
            if action.action_type != ActionType.DELETE:
                filtered.append(action)
                continue

            removed = False
            for raw_dir in gitignore_dirs:
                prefix = f"{raw_dir}/"
                if action.source.startswith(prefix):
                    involved_gitignore = [
                        a for a in actions if a.action_type == ActionType.ADD_GITIGNORE and _normalize_dir(a.source) == raw_dir
                    ]
                    for gi in involved_gitignore:
                        gi.conflict = True

                    logger.warning(
                        "Redundant DELETE under gitignored dir %s: removed %s",
                        raw_dir,
                        action.source,
                    )
                    self._record(
                        conflict_type="REDUNDANT_DELETE_UNDER_GITIGNORE_DIR",
                        source=action.source,
                        resolution=f"removed DELETE because {raw_dir}/ is gitignored",
                        actions_involved=[action, *involved_gitignore],
                    )
                    removed = True
                    break

            if not removed:
                filtered.append(action)

        return filtered

    def _reorder_move_chain(self, actions: list[Action]) -> list[Action]:
        """Topological sort so move dependencies execute in correct order."""
        move_actions: list[tuple[int, Action]] = [(i, a) for i, a in enumerate(actions) if a.action_type == ActionType.MOVE]
        if len(move_actions) <= 1:
            return actions

        # After duplicate resolution there should be one MOVE per source; if not, pick first per source.
        source_to_node: dict[str, int] = {}
        nodes: list[tuple[int, Action]] = []
        for idx, action in move_actions:
            if action.source in source_to_node:
                continue
            source_to_node[action.source] = len(nodes)
            nodes.append((idx, action))

        n = len(nodes)
        adj: list[list[int]] = [[] for _ in range(n)]
        indeg = [0] * n

        for node_idx, (_orig_idx, action) in enumerate(nodes):
            dest = action.destination
            if not dest:
                continue
            dep = source_to_node.get(dest)
            if dep is None:
                continue
            # dest->... must run before ...->dest
            adj[dep].append(node_idx)
            indeg[node_idx] += 1

        q: deque[int] = deque(sorted([i for i, d in enumerate(indeg) if d == 0], key=lambda i: nodes[i][0]))
        ordered: list[int] = []
        while q:
            u = q.popleft()
            ordered.append(u)
            for v in adj[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)

        if len(ordered) != n:
            cycle_sources = [nodes[i][1].source for i in range(n) if indeg[i] > 0]
            for i in range(n):
                if indeg[i] > 0:
                    nodes[i][1].conflict = True
            logger.warning("MOVE chain has a cycle; leaving MOVE order unchanged: %s", cycle_sources)
            self._record(
                conflict_type="MOVE_CHAIN_CYCLE",
                source=";".join(cycle_sources),
                resolution="cycle detected; MOVE order left unchanged; marked involved MOVE actions conflict",
                actions_involved=[nodes[i][1] for i in range(n) if indeg[i] > 0],
            )
            return actions

        sorted_nodes = [nodes[i] for i in ordered]
        sorted_moves = [a for _idx, a in sorted_nodes]

        if [a for _idx, a in nodes] == sorted_moves:
            return actions

        # Replace MOVE actions in-place (preserves non-MOVE relative positioning).
        it = iter(sorted_moves)
        out: list[Action] = []
        for action in actions:
            if action.action_type == ActionType.MOVE:
                out.append(next(it))
            else:
                out.append(action)

        logger.warning("Reordered MOVE chain to satisfy dependencies")
        self._record(
            conflict_type="MOVE_CHAIN_REORDERED",
            source="",
            resolution="reordered MOVE actions so dependent moves run first",
            actions_involved=sorted_moves,
        )
        for a in sorted_moves:
            a.conflict = True
        return out

    def conflict_report(self) -> list[dict]:
        """
        Return list of {type, source, resolution, actions_involved}
        for every conflict that was detected (even if auto-resolved).
        """
        return list(self._conflicts)

