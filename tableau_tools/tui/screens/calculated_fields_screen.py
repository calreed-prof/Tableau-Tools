"""Textual screen for browsing and editing calculated fields."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static, TextArea

from ...calculated_fields import (
    _humanize_formulas,
    collect_calculated_fields,
    set_formula,
    write_csv,
)
from ...common import Workbook, backup, load_workbook, save_workbook


class CalculatedFieldsScreen(Screen):
    """Browse, edit, and save calculated field formulas."""

    TITLE = "Calculated Fields"
    CSS = """
    #calc-status   { padding: 0 1; color: $text-muted; }
    #calc-banner   { padding: 0 1; }
    #calc-table    { height: 40%; }
    #calc-area     { height: 1fr; }
    #calc-actions  { height: auto; padding: 0 1; align: left middle; }
    #calc-actions Button { margin-right: 1; }
    .read-only-banner { background: $warning 30%; color: $text; }
    .hidden { display: none; }
    """

    BINDINGS = [
        Binding("e", "focus_editor", "Edit"),
        Binding("s", "stage", "Stage row"),
        Binding("w", "write", "Save workbook"),
        Binding("r", "reload", "Reload"),
        Binding("x", "export_csv", "Export CSV"),
        Binding("escape", "back", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, workbook_path: Path) -> None:
        super().__init__()
        self.workbook_path = workbook_path
        self._wb: Workbook | None = None
        self._entries: list[dict] = []
        self._staged: set[int] = set()
        self._row_dirty = False
        self._current_idx: int | None = None

    @property
    def _modified(self) -> bool:
        return bool(self._staged)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("", id="calc-status")
        yield Static("", id="calc-banner", classes="read-only-banner hidden")
        table = DataTable(id="calc-table", cursor_type="row", zebra_stripes=True)
        table.add_columns("#", "Datasource", "Name", "Param?", "Formula preview")
        yield table
        yield TextArea.code_editor("", language="sql", id="calc-area", show_line_numbers=True)
        yield Horizontal(
            Button("Stage edit", id="btn-stage", variant="primary", classes="hidden"),
            Button("Discard edit", id="btn-discard", classes="hidden"),
            Button("Save workbook", id="btn-save", variant="success", classes="hidden"),
            id="calc-actions",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        try:
            self._wb = load_workbook(self.workbook_path)
        except SystemExit as exc:
            self.app.notify(str(exc), severity="error")
            self.app.pop_screen()
            return
        self._entries = collect_calculated_fields(self._wb.root)
        _humanize_formulas(self._entries)
        self._staged.clear()
        self._row_dirty = False
        self._current_idx = None
        self._refresh()

    def _refresh(self) -> None:
        dirty = f" [{len(self._staged)} unsaved]" if self._staged else ""
        self.query_one("#calc-status", Static).update(
            f"{self.workbook_path.name}  —  {len(self._entries)} calculated field(s){dirty}"
        )
        table = self.query_one("#calc-table", DataTable)
        table.clear()
        for i, e in enumerate(self._entries, 1):
            preview = " ".join(e["formula"].split())[:80]
            mark = "● " if i - 1 in self._staged else ""
            table.add_row(
                str(i),
                e["datasource"][:30],
                f"{mark}{e['name']}"[:40],
                "yes" if e["is_parameter"] else "",
                preview,
                key=str(i - 1),
            )
        if self._entries:
            table.focus()
            table.move_cursor(row=0)
            self._show(0)
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        stage = self.query_one("#btn-stage", Button)
        discard = self.query_one("#btn-discard", Button)
        save = self.query_one("#btn-save", Button)

        for btn, show in (
            (stage, self._row_dirty),
            (discard, self._row_dirty),
            (save, self._modified),
        ):
            btn.set_class(not show, "hidden")

        if self._modified:
            save.label = f"Save workbook ({len(self._staged)})"

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._show(int(event.row_key.value))

    def _show(self, idx: int) -> None:
        if not (0 <= idx < len(self._entries)):
            return
        entry = self._entries[idx]
        area = self.query_one("#calc-area", TextArea)
        banner = self.query_one("#calc-banner", Static)

        self._current_idx = idx
        area.text = entry["formula"]
        # text setter posts a Changed event — on_text_area_changed compares
        # against entry["formula"] so dirty flips back to False on its own.

        if entry["is_parameter"]:
            area.read_only = True
            banner.update("Parameter — read-only in this editor.")
            banner.remove_class("hidden")
        else:
            area.read_only = False
            banner.add_class("hidden")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self._current_idx is None:
            return
        entry = self._entries[self._current_idx]
        new_dirty = event.text_area.text != entry["formula"]
        if new_dirty != self._row_dirty:
            self._row_dirty = new_dirty
            self._refresh_actions()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-stage":
            self.action_stage()
        elif event.button.id == "btn-discard":
            self._discard_row()
        elif event.button.id == "btn-save":
            self.action_write()

    def _discard_row(self) -> None:
        if self._current_idx is None:
            return
        entry = self._entries[self._current_idx]
        self.query_one("#calc-area", TextArea).text = entry["formula"]
        self.app.notify(f"Discarded edit on row #{self._current_idx + 1}.")

    def action_focus_editor(self) -> None:
        if self._current_idx is None:
            return
        entry = self._entries[self._current_idx]
        if entry["is_parameter"]:
            self.app.notify("Parameters are read-only.", severity="warning")
            return
        self.query_one("#calc-area", TextArea).focus()

    def action_stage(self) -> None:
        if self._current_idx is None:
            self.app.notify("Pick a row first.", severity="warning")
            return
        entry = self._entries[self._current_idx]
        if entry["is_parameter"]:
            self.app.notify("Parameters are read-only.", severity="warning")
            return
        new_text = self.query_one("#calc-area", TextArea).text
        if new_text == entry["formula"]:
            self.app.notify("No changes to stage.")
            return
        set_formula(self._entries, entry, new_text)
        self._staged.add(self._current_idx)
        self._row_dirty = False
        cur = self._current_idx
        self._refresh()
        table = self.query_one("#calc-table", DataTable)
        table.move_cursor(row=cur)
        self.app.notify(
            f"Staged row #{cur + 1}. Click 'Save workbook' to write to disk."
        )

    def action_write(self) -> None:
        if not self._modified:
            self.app.notify("Nothing to save.")
            return
        if self._wb is None:
            return
        try:
            backup(self.workbook_path)
            save_workbook(self._wb)
        except Exception as exc:
            self.app.notify(f"Save failed: {exc}", severity="error")
            return
        count = len(self._staged)
        self._staged.clear()
        self._refresh()
        self.app.notify(
            f"Saved {count} edit(s) to {self.workbook_path.name} (backup: .bak)"
        )

    def action_reload(self) -> None:
        if self._modified:
            self.app.notify(
                "Unsaved edits pending — save first, or back out to discard.",
                severity="warning",
            )
            return
        self._load()

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
        if self._modified:
            self.app.notify(
                "Unsaved edits pending — click 'Save workbook' first.",
                severity="warning",
            )
            return
        self.app.pop_screen()

    def action_quit_app(self) -> None:
        if self._modified:
            self.app.notify(
                "Unsaved edits pending — click 'Save workbook' first, then 'q' again.",
                severity="warning",
            )
            return
        self.app.exit()
