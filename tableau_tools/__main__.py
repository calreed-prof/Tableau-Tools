"""Interactive launcher for the Tableau Tools package.

Run with:
    python -m tableau_tools                       # full TUI
    python -m tableau_tools <path/to/workbook>    # TUI pre-loaded with a workbook
"""

from __future__ import annotations

import sys
from pathlib import Path

from .common import validate_workbook_path
from .tui.app import TableauToolsApp


def main() -> None:
    workbook: Path | None = None
    if len(sys.argv) > 1:
        workbook = validate_workbook_path(sys.argv[1])
    TableauToolsApp(workbook_path=workbook).run()


if __name__ == "__main__":
    main()
