"""Textual screen wrapping the SQL editor logic."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    LoadingIndicator,
    Static,
    TextArea,
)

from ...common import Workbook, backup, load_workbook, save_workbook
from ...sql_editor import (
    _KIND_LABEL,
    _expand_published_ds,
    _fetch_published_ds,
    collect_published_datasources,
    collect_sql_entries,
    get_sql,
    set_sql,
)


class SqlEditorScreen(Screen):
    """Browse + edit Initial SQL, Custom SQL, and published-DS SQL."""

    TITLE = "SQL Editor"
    CSS = """
    #sql-status { padding: 0 1; color: $text-muted; }
    #sql-table { height: 40%; }
    #sql-area  { height: 1fr; }
    #sql-loading { align: center middle; height: auto; padding: 1; }
    .read-only-banner { background: $warning 30%; color: $text; padding: 0 1; }
    .hidden { display: none; }
    """

    BINDINGS = [
        Binding("e", "focus_editor", "Edit"),
        Binding("s", "stage", "Stage row"),
        Binding("w", "write", "Write workbook"),
        Binding("d", "download", "Download published DS"),
        Binding("r", "reload", "Reload"),
        Binding("escape", "back", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, workbook_path: Path) -> None:
        super().__init__()
        self.workbook_path = workbook_path
        self._wb: Workbook | None = None
        self._entries: list[dict] = []
        self._modified = False
        self._row_dirty = False
        self._current_idx: int | None = None

    # ------------------------------------------------------------------ compose

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("", id="sql-status")
        yield Static("", id="sql-banner", classes="read-only-banner hidden")
        table = DataTable(id="sql-table", cursor_type="row", zebra_stripes=True)
        table.add_columns("#", "Type", "Datasource", "Preview")
        yield table
        yield TextArea.code_editor("", language="sql", id="sql-area", show_line_numbers=True)
        yield Container(LoadingIndicator(), Static("Downloading published datasource…"), id="sql-loading", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    # -------------------------------------------------------------------- data

    def _load(self) -> None:
        try:
            self._wb = load_workbook(self.workbook_path)
        except SystemExit as exc:
            self.app.notify(str(exc), severity="error")
            self.app.pop_screen()
            return
        self._entries = collect_sql_entries(self._wb.root) + collect_published_datasources(self._wb.root)
        self._modified = False
        self._row_dirty = False
        self._current_idx = None
        self._refresh_status()
        self._refresh_table()

    def _refresh_status(self) -> None:
        dirty = " [unsaved workbook edits]" if self._modified else ""
        self.query_one("#sql-status", Static).update(
            f"{self.workbook_path.name}  —  {len(self._entries)} SQL block(s){dirty}"
        )

    def _refresh_table(self) -> None:
        table = self.query_one("#sql-table", DataTable)
        table.clear()
        if not self._entries:
            self.app.notify("No SQL blocks or published datasources found.")
            return
        for i, e in enumerate(self._entries, 1):
            label = _KIND_LABEL.get(e["kind"], e["kind"])
            if e.get("read_only"):
                label = f"{label}*"
            ds = e["ds_name"][:40]
            preview = " ".join(e["display_sql"].split())[:80]
            if e["kind"] != "published_datasource":
                preview = preview + ("…" if len(e["display_sql"]) > 80 else "")
            table.add_row(str(i), label, ds, preview, key=str(i - 1))
        table.focus()
        table.move_cursor(row=0)

    # ----------------------------------------------------------------- events

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._show_row(int(event.row_key.value))

    def _show_row(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._entries):
            return
        entry = self._entries[idx]
        area = self.query_one("#sql-area", TextArea)
        banner = self.query_one("#sql-banner", Static)

        self._current_idx = idx
        self._row_dirty = False

        if entry["kind"] == "published_datasource":
            area.text = "(Published datasource — press 'd' to download and expand its SQL inline.)"
            area.read_only = True
            banner.update("Published datasource — press 'd' to download.")
            banner.remove_class("hidden")
            return

        area.text = get_sql(entry)
        area.read_only = bool(entry.get("read_only"))
        if entry.get("read_only"):
            banner.update("Read-only (from published datasource — edits are not saved).")
            banner.remove_class("hidden")
        else:
            banner.add_class("hidden")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._row_dirty = True

    # ----------------------------------------------------------------- actions

    def action_focus_editor(self) -> None:
        if self._current_idx is None:
            return
        entry = self._entries[self._current_idx]
        if entry.get("read_only") or entry["kind"] == "published_datasource":
            self.app.notify("Row is read-only.", severity="warning")
            return
        self.query_one("#sql-area", TextArea).focus()

    def action_stage(self) -> None:
        if self._current_idx is None:
            self.app.notify("Pick a row first.", severity="warning")
            return
        entry = self._entries[self._current_idx]
        if entry["kind"] == "published_datasource" or entry.get("read_only"):
            self.app.notify("Row is read-only.", severity="warning")
            return
        new_sql = self.query_one("#sql-area", TextArea).text
        if new_sql.strip() == get_sql(entry).strip():
            self.app.notify("No changes to stage.")
            return
        set_sql(entry, new_sql)
        entry["display_sql"] = new_sql.strip()[:120]
        self._modified = True
        self._row_dirty = False
        self._refresh_status()
        cur = self._current_idx
        self._refresh_table()
        table = self.query_one("#sql-table", DataTable)
        table.move_cursor(row=cur)
        self.app.notify(f"Staged row #{cur + 1}. Press 'w' to write workbook.")

    def action_write(self) -> None:
        if not self._modified:
            self.app.notify("Nothing to write.")
            return
        if self._wb is None:
            return
        try:
            backup(self.workbook_path)
            save_workbook(self._wb)
        except Exception as exc:
            self.app.notify(f"Save failed: {exc}", severity="error")
            return
        self._modified = False
        self._refresh_status()
        self.app.notify(f"Saved {self.workbook_path.name} (backup: .bak)")

    def action_reload(self) -> None:
        if self._modified:
            self.app.notify("Discard unsaved edits with Esc/back; reload skipped.", severity="warning")
            return
        self._load()

    def action_back(self) -> None:
        if self._modified:
            self.app.notify("Unsaved staged edits. Press 'w' to save or 'r' to discard via reload.", severity="warning")
            return
        self.app.pop_screen()

    def action_quit_app(self) -> None:
        if self._modified:
            self.app.notify("Unsaved staged edits — press 'w' to save first, then 'q' again.", severity="warning")
            return
        self.app.exit()

    # ------------------------------------------------------------- published DS

    def action_download(self) -> None:
        if self._current_idx is None:
            return
        entry = self._entries[self._current_idx]
        if entry["kind"] != "published_datasource":
            self.app.notify("Selected row is not a published datasource.", severity="warning")
            return
        self.query_one("#sql-loading").remove_class("hidden")
        self._do_download(self._current_idx, entry)

    @work(thread=True, exclusive=True, group="download")
    def _do_download(self, idx: int, entry: dict) -> None:
        ds_root = _fetch_published_ds(entry)
        self.app.call_from_thread(self._after_download, idx, entry, ds_root)

    def _after_download(self, idx: int, entry: dict, ds_root) -> None:
        self.query_one("#sql-loading").add_class("hidden")
        if ds_root is None:
            self.app.notify("Download failed (see terminal for details).", severity="error")
            return
        sub = _expand_published_ds(ds_root, entry["published_name"])
        self._entries[idx : idx + 1] = sub
        self._refresh_table()
        self.app.notify(f"Loaded {len(sub)} SQL block(s) from '{entry['published_name']}'.")
