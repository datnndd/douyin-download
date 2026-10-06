import difflib
from pathlib import Path

original_path = Path("src/web/core/config.py")
proposed_path = Path(".agents/teamwork/teamwork_preview_explorer_m1_it2_1/proposed_config.py")
patch_path = Path(".agents/teamwork/teamwork_preview_explorer_m1_it2_1/config_remediation.patch")

original_lines = original_path.read_text(encoding="utf-8").splitlines(keepends=True)
proposed_lines = proposed_path.read_text(encoding="utf-8").splitlines(keepends=True)

diff = difflib.unified_diff(
    original_lines,
    proposed_lines,
    fromfile="a/src/web/core/config.py",
    tofile="b/src/web/core/config.py",
)

patch_content = "".join(diff)
patch_path.write_text(patch_content, encoding="utf-8")
print(f"Generated patch of {len(patch_content)} bytes to {patch_path}")
