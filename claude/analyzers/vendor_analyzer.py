import logging
from pathlib import Path

from core.models import Action, ActionType, AnalysisResult, FileRecord, RiskLevel

logger = logging.getLogger(__name__)

VENDOR_PATTERNS = [
    "vendor/",
    "node_modules/",
    "bower_components/",
]


class VendorAnalyzer:
    def __init__(
        self,
        records: dict[str, FileRecord],
        project_dir: Path,
    ) -> None:
        self._records = records
        self._project_dir = project_dir

    def analyze(self) -> AnalysisResult:
        vendor_roots = self._find_vendor_roots()
        total_files = len(self._records)
        total_vendor_files = sum(len(files) for files in vendor_roots.values())

        vendor_roots_meta: dict[str, dict] = {}
        actions: list[Action] = []

        for root, files in vendor_roots.items():
            file_count = len(files)
            pct = round(file_count / total_files * 100, 1) if total_files > 0 else 0.0
            vendor_roots_meta[f"{root}/"] = {"file_count": file_count, "pct": pct}

            reason = (
                f"{root}/ contains {file_count} files ({pct}% of project). "
                f"Add to .gitignore."
            )
            actions.append(
                Action(
                    action_type=ActionType.ADD_GITIGNORE,
                    source=root,
                    destination=None,
                    risk_level=RiskLevel.LOW,
                    reason=reason,
                )
            )

        metadata = {
            "vendor_roots": vendor_roots_meta,
            "total_vendor_files": total_vendor_files,
            "total_files": total_files,
        }

        return AnalysisResult(
            analyzer_name="vendor_analyzer",
            actions=actions,
            metadata=metadata,
        )

    def _find_vendor_roots(self) -> dict[str, list[str]]:
        roots: dict[str, list[str]] = {}
        for path in self._records:
            is_vendor, matched_root = self._is_vendor_path(path)
            if is_vendor:
                roots.setdefault(matched_root, []).append(path)
        return roots

    def _is_vendor_path(self, path: str) -> tuple[bool, str]:
        parts = Path(path).parts
        for i, part in enumerate(parts[:-1]):  # exclude the filename itself
            candidate = part + "/"
            if candidate in VENDOR_PATTERNS:
                # Build the root as prefix up to and including this component
                matched_root = "/".join(parts[: i + 1])
                return True, matched_root
        return False, ""
