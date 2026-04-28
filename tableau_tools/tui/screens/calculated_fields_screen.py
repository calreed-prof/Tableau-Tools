"""Textual screen for browsing calculated fields."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, TextArea

from ...calculated_fields import (
    _humanize_formulas,
    collect_calculated_fields,
    write_csv,
)
from ...common import load_workbook


class CalculatedFieldsScreen(Screen):
    """Read-only browser for calculated fields with CSV export."""

    TITLE = "Calculated Fields"
    CSS = """
    #calc-status { padding: 0 1; color: $text-muted; }
    #calc-table  { height: 50%; }
    #calc-area   { height: 1fr; }
    """

    BINDINGS = [
        Binding("x", "export_csv", "Export CSV"),
        Binding("escape", "back", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, workbook_path: Path) -> None:
        super().__init__()
        self.workbook_path = workbook_path
        self._entries: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("", id="calc-status")
        table = DataTable(id="calc-table", cursor_type="row", zebra_stripes=True)
        table.add_columns("#", "Datasource", "Name", "Param?", "Formula preview")
        yield table
        yield TextArea.code_editor("", language="sql", id="calc-area", read_only=True, show_line_numbers=True)
        yield Footer()

    def on_mount(self) -> None:
        try:
            wb = load_workbook(self.workbook_path)
        except SystemExit as exc:
            self.app.notify(str(exc), severity="error")
            self.app.pop_screen()
            return
        self._entries = collect_calculated_fields(wb.root)
        _humanize_formulas(self._entries)
        self._refresh()

    def _refresh(self) -> None:
        self.query_one("#calc-status", Static).update(
            f"{self.workbook_path.name}  —  {len(self._entries)} calculated field(s)"
        )
        table = self.query_one("#calc-table", DataTable)
        table.clear()
        for i, e in enumerate(self._entries, 1):
            preview = " ".join(e["formula"].split())[:80]
            table.add_row(
                str(i),
                e["datasource"][:30],
                e["name"][:40],
                "yes" if e["is_parameter"] else "",
                preview,
                key=str(i - 1),
            )
        if self._entries:
            table.focus()
            table.move_cursor(row=0)
            self._show(0)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._show(int(event.row_key.value))

    def _show(self, idx: int) -> None:
        if 0 <= idx < len(self._entries):
            self.query_one("#calc-area", TextArea).text = self._entries[idx]["formula"]

    def action_export_csv(self) -> None:
        if not self._entries:
            self.app.notify("Nothing to export.")
            return
        out = self.workbook_path.with_suffix(self.workbook_path.suffix + ".calcs.csv")
        try:
            write_csv(self._entries, out)
        except Exception as exc:
            self.app.notify(f"CSV write failed: {exc}", severity="error")
            return
        self.app.notify(f"Wrote {out}")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit_app(self) -> None:
        self.app.exit()
