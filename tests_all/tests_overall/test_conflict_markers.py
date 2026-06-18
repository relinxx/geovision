"""
Test to detect unresolved Git merge conflict markers in Python files.

This test scans all Python files for conflict markers:
- <<<<<<< (start of conflict)
- ======= (separator, when used as conflict marker)
- >>>>>>> (end of conflict)
"""

from __future__ import annotations

import os
from pathlib import Path


def _is_conflict_separator_line(line: str) -> bool:
    """
    Determine if a line with ======= is a conflict marker or decorative separator.
    
    Conflict markers are exactly '=======' or start with '======= '
    Decorative comments usually have other content like '# =======' or are within text.
    """
    stripped = line.strip()
    # Pure conflict marker: exactly 7 equals signs, or 7 equals followed by space and text
    if stripped == "=======" * 7:
        return True
    if stripped.startswith("=======" * 7) and stripped[7] in ("", " ", "\t"):
        return True
    return False


def test_no_conflict_markers_in_python_files():
    """
    Scan all Python files for Git merge conflict markers.
    
    Fails if any unresolved conflict markers are found.
    """
    backend_dir = Path(__file__).parent.parent
    python_files = list(backend_dir.rglob("*.py"))
    
    conflicts_found = []
    
    for file_path in python_files:
        # Skip hidden directories and virtual environments
        if any(part.startswith(".") for part in file_path.parts):
            continue
        if ".venv" in str(file_path) or "__pycache__" in str(file_path):
            continue
            
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            for line_num, line in enumerate(lines, 1):
                # Check for conflict markers
                if line.startswith("<<<<<<< "):
                    conflicts_found.append(f"{file_path}:{line_num}: {line[:50]}")
                elif line.startswith(">>>>>>> "):
                    conflicts_found.append(f"{file_path}:{line_num}: {line[:50]}")
                elif _is_conflict_separator_line(line):
                    conflicts_found.append(f"{file_path}:{line_num}: {line[:50]}")
        except Exception as e:
            # If we can't read a file, note it but don't fail the test for this
            print(f"Warning: Could not read {file_path}: {e}")
    
    if conflicts_found:
        error_msg = "Unresolved merge conflict markers found:\n" + "\n".join(conflicts_found)
        raise AssertionError(error_msg)
