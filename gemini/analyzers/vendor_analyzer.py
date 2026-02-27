import os
from pathlib import Path
from typing import Dict, List, Tuple

from core.models import Action, ActionType, AnalysisResult, FileRecord, RiskLevel

# Vendor directory patterns to detect
VENDOR_PATTERNS = [
    "vendor/",
    "node_modules/",
    "bower_components/",
]
STRIPPED_PATTERNS = [p.strip("/") for p in VENDOR_PATTERNS]

class VendorAnalyzer:
    def __init__(
        self,
        records: Dict[str, FileRecord],
        project_dir: Path
    ) -> None:
        self.records = records
        self.project_dir = project_dir

    def _is_vendor_path(self, path_str: str) -> Tuple[bool, str]:
        """
        Check if path contains a vendor directory component.
        Returns (is_vendor, matched_root).
        e.g. "vendor/lib/x.php" -> (True, "vendor")
             "test/vendor/y.php" -> (True, "test/vendor")
        """
        try:
            parts = Path(path_str).parts
        except ValueError:
            return False, "" # Handles potential invalid path characters

        for i, part in enumerate(parts):
            if part in STRIPPED_PATTERNS:
                # The root is the path up to and including the vendor component
                root = os.path.join(*parts[:i+1])
                return True, root
        return False, ""

    def _find_vendor_roots(self) -> Dict[str, List[str]]:
        """Return {vendor_root: [file_paths]} for all detected vendor dirs."""
        vendor_roots: Dict[str, List[str]] = {}
        for path_str in self.records:
            is_vendor, root = self._is_vendor_path(path_str)
            if is_vendor:
                if root not in vendor_roots:
                    vendor_roots[root] = []
                vendor_roots[root].append(path_str)
        return vendor_roots

    def analyze(self) -> AnalysisResult:
        """
        1. Find all unique vendor roots (e.g. "vendor", "test/vendor")
           by checking if any path component matches VENDOR_PATTERNS prefixes.
        2. Count files per vendor root.
        3. Calculate percentage: vendor_files / total_files * 100.
        4. For each vendor root, produce one ADD_GITIGNORE Action (LOW risk).
        5. Return AnalysisResult with:
             analyzer_name = "vendor_analyzer"
             actions = [one ADD_GITIGNORE per vendor root]
             metadata = {
               "vendor_roots": { "vendor/": {"file_count": N, "pct": 83.2} },
               "total_vendor_files": N,
               "total_files": N
             }
        """
        vendor_roots_files = self._find_vendor_roots()
        total_files = len(self.records)
        total_vendor_files = sum(len(files) for files in vendor_roots_files.values())

        actions = []
        metadata_roots = {}

        if total_files == 0:
            return AnalysisResult(
                analyzer_name="vendor_analyzer",
                actions=[],
                metadata={
                    "vendor_roots": {},
                    "total_vendor_files": 0,
                    "total_files": 0,
                },
            )

        for root, files in vendor_roots_files.items():
            file_count = len(files)
            percentage = (file_count / total_files) * 100 if total_files > 0 else 0
            
            # The key for metadata should have a trailing slash for directories
            metadata_key = f"{root.replace(os.sep, '/')}/"
            metadata_roots[metadata_key] = {
                "file_count": file_count,
                "pct": round(percentage, 2),
            }

            reason = (
                f"{root.replace(os.sep, '/')}/ contains {file_count} files ({percentage:.1f}% of project). "
                "Add to .gitignore."
            )
            
            action = Action(
                action_type=ActionType.ADD_GITIGNORE,
                source=root,  # source is the root dir name, no trailing slash
                destination=None,
                risk_level=RiskLevel.LOW,
                reason=reason,
            )
            actions.append(action)

        metadata = {
            "vendor_roots": metadata_roots,
            "total_vendor_files": total_vendor_files,
            "total_files": total_files,
        }

        return AnalysisResult(
            analyzer_name="vendor_analyzer",
            actions=actions,
            metadata=metadata,
        )
