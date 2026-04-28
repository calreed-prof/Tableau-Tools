# SOP — Adding a new tool

This package is a hub for small, focused utilities that read or modify Tableau
workbooks (`.twb` / `.twbx`) without launching Tableau Desktop. Every tool lives
in two places that share the same pure-logic functions:

- a **module** under `tableau_tools/<your_tool>.py` exposing `run(...)` and
  `main()` so the tool also works headlessly:
  `python -m tableau_tools.<your_tool> <workbook>`
- a **Textual screen** under `tableau_tools/tui/screens/<your_tool>_screen.py`
  registered in `tableau_tools/tui/tools.py` so it shows up in the launcher.

Before you build anything new, check whether Tableau Desktop already covers the
workflow. Build only when bulk, headless, or audit value is real (e.g. one-shot
batch edits across many workbooks, CI checks, exports Desktop won't produce).

---

## 1. Module template

Create `tableau_tools/<your_tool>.py`:

```python
"""One-line description of what this tool does.

Usage:
    python -m tableau_tools.<your_tool> <workbook.twb|.twbx>
"""

from __future__ import annotations

import sys
from pathlib import Path

from lxml import etree

from .common import backup, load_workbook, save_workbook, validate_workbook_path


def collect_things(root: etree._Element) -> list[dict]:
    """Pure read function. The TUI screen imports this directly."""
    out: list[dict] = []
    for ds in root.iter("datasource"):
        ...
    return out


def apply_change(entry: dict, new_value: str) -> None:
    """Pure mutation function. The TUI screen imports this directly."""
    ...


def run(workbook_path: Path) -> None:
    """Headless entry point. Called by main() and by tests."""
    wb = load_workbook(workbook_path)
    things = collect_things(wb.root)
    # ... do work ...
    if changed:
        backup(workbook_path)        # MANDATORY before save_workbook
        save_workbook(wb)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    run(validate_workbook_path(sys.argv[1]))


if __name__ == "__main__":
    main()
```

Rules:

- Use `common.load_workbook` / `save_workbook` / `backup`. Never re-implement
  zip handling — the existing helpers preserve every non-XML zip member
  byte-for-byte so Tableau Desktop accepts the file.
- Mutating tools **must** call `backup(path)` before `save_workbook(wb)`.
- Keep `collect_*` and `apply_*` as pure functions over `etree._Element`. The
  TUI screen will import them directly.

---

## 2. Screen template

Create `tableau_tools/tui/screens/<your_tool>_screen.py`:

```python
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, TextArea

from ...common import load_workbook
from ...your_tool import collect_things


class YourToolScreen(Screen):
    TITLE = "Your Tool"

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, workbook_path: Path) -> None:
        super().__init__()
        self.workbook_path = workbook_path

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("", id="status")
        table = DataTable(cursor_type="row", zebra_stripes=True)
        table.add_columns("#", "Name", "Detail")
        yield table
        yield Footer()

    def on_mount(self) -> None:
        wb = load_workbook(self.workbook_path)
        things = collect_things(wb.root)
        self.query_one("#status", Static).update(f"{self.workbook_path.name} — {len(things)} item(s)")
        table = self.query_one(DataTable)
        for i, t in enumerate(things, 1):
            table.add_row(str(i), t["name"], t["detail"], key=str(i - 1))

    def action_back(self) -> None:
        self.app.pop_screen()
```

Conventions:

- The screen receives `workbook_path: Path` in `__init__`. The launcher already
  pushed the workbook picker; you don't need to handle file selection.
- For long-running work (REST calls, large parses), wrap in
  `@work(thread=True)` and post results back via `self.app.call_from_thread`.
- For read-only views over SQL or formulas, use
  `TextArea.code_editor("", language="sql", read_only=True)` — search and copy
  still work; it's better than disabling the widget.
- Use `self.app.notify("...", severity="warning"|"error"|None)` for user
  feedback instead of inline status widgets.

---

## 3. Register the tool

Append one line to `tableau_tools/tui/tools.py`:

```python
from .screens.your_tool_screen import YourToolScreen

TOOLS: list[ToolEntry] = [
    ToolEntry("Edit SQL",         "Initial / Custom SQL / Published DS", SqlEditorScreen),
    ToolEntry("List calc fields", "Calculated fields (export to CSV)",   CalculatedFieldsScreen),
    ToolEntry("Your tool",        "Short tagline shown in the launcher", YourToolScreen),
]
```

That's it — no other launcher edits required.

---

## 4. Testing checklist

Before opening a PR:

1. `python -m tableau_tools` — your tool appears in the launcher; arrow keys
   reach it; Enter opens it.
2. Open a sample `.twb` and a `.twbx`. Both load without errors.
3. If your tool writes: save, then open the workbook in Tableau Desktop and
   confirm
   - your change persisted,
   - the file isn't corrupted (other extracts/images/thumbnails intact),
   - a `.bak` exists next to the workbook.
4. `python -m tableau_tools.<your_tool> <workbook>` — argv entry point still
   works headlessly.
5. Update `README.md` (Tools table + Direct invocation section) and
   `CLAUDE.md` if you added new shared concepts.
