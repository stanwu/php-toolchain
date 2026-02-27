from __future__ import annotations

from pathlib import Path
from typing import Any

from core.models import Action, ActionType, AnalysisResult, FileRecord, RiskLevel

VENDOR_PATTERNS = [
    "vendor/",
    "node_modules/",
    "bower_components/",
]


class VendorAnalyzer:
    def __init__(self, records: dict[str, FileRecord], project_dir: Path) -> None:
        self._records = records
        self._project_dir = project_dir

        self._vendor_dir_names = tuple(p.rstrip("/").rstrip("\\") for p in VENDOR_PATTERNS)

    def analyze(self) -> AnalysisResult:
        vendor_roots_to_files = self._find_vendor_roots()

        total_files = len(self._records)
        total_vendor_files = sum(len(paths) for paths in vendor_roots_to_files.values())

        vendor_roots: dict[str, dict[str, Any]] = {}
        actions: list[Action] = []

        for root in sorted(vendor_roots_to_files):
            file_count = len(vendor_roots_to_files[root])
            pct = 0.0 if total_files == 0 else (file_count / total_files) * 100.0
            pct_rounded = round(pct, 1)
            vendor_roots[root] = {"file_count": file_count, "pct": pct_rounded}

            actions.append(
                Action(
                    action_type=ActionType.ADD_GITIGNORE,
                    source=root,
                    destination=None,
                    risk_level=RiskLevel.LOW,
                    reason=(
                        f"{root}/ contains {file_count} files ({pct_rounded:.1f}% of project). "
                        "Add to .gitignore."
                    ),
                )
            )

        return AnalysisResult(
            analyzer_name="vendor_analyzer",
            actions=actions,
            metadata={
                "vendor_roots": vendor_roots,
                "total_vendor_files": total_vendor_files,
                "total_files": total_files,
            },
        )

    def _find_vendor_roots(self) -> dict[str, list[str]]:
        vendor_roots: dict[str, list[str]] = {}

        for rel_path in self._records:
            is_vendor, root = self._is_vendor_path(rel_path)
            if not is_vendor:
                continue
            vendor_roots.setdefault(root, []).append(rel_path)

        return vendor_roots

    def _is_vendor_path(self, path: str) -> tuple[bool, str]:
        normalized = path.replace("\\", "/").lstrip("./")
        parts = [p for p in normalized.split("/") if p]

        for idx, part in enumerate(parts):
            if part in self._vendor_dir_names:
                return True, "/".join(parts[: idx + 1])

        return False, ""
