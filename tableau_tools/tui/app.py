"""Main Textual app for Tableau Tools."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from .screens.workbook_picker import WorkbookPickerScreen
from .tools import TOOLS, ToolEntry


class _ToolsList(ListView):
    """ListView that knows which ToolEntry each row maps to."""

    def __init__(self) -> None:
        items = [
            ListItem(Static(f"[b]{t.label}[/]\n  [dim]{t.description}[/]"), id=f"tool-{i}")
            for i, t in enumerate(TOOLS)
        ]
        super().__init__(*items, id="tools-list")


class LauncherScreen(Screen):
    TITLE = "Tableau Tools"
    SUB_TITLE = "Edit and inspect Tableau workbooks"

    CSS = """
    #launcher-box { padding: 1 2; height: 1fr; }
    #launcher-hint { color: $text-muted; padding: 0 1 1 1; }
    #tools-list { border: round $accent; }
    """

    BINDINGS = [
        Binding("enter", "open", "Open", priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="launcher-box"):
            yield Static("Pick a tool. A workbook picker opens after you choose.", id="launcher-hint")
            yield _ToolsList()
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(_ToolsList).focus()

    def action_open(self) -> None:
        lv = self.query_one(_ToolsList)
        idx = lv.index
        if idx is None:
            return
        self._launch(TOOLS[idx])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(_ToolsList).index
        if idx is None:
            return
        self._launch(TOOLS[idx])

    def _launch(self, tool: ToolEntry) -> None:
        existing = getattr(self.app, "workbook_path", None)
        if existing is not None:
            self.app.push_screen(tool.screen_factory(existing))
            return

        def on_picked(path: Path | None) -> None:
            if path is None:
                return
            self.app.workbook_path = path
            self.app.push_screen(tool.screen_factory(path))

        self.app.push_screen(WorkbookPickerScreen(), on_picked)


class TableauToolsApp(App):
    """Top-level Textual app."""

    TITLE = "Tableau Tools"
    CSS = """
    Screen { background: $background; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, workbook_path: Path | None = None) -> None:
        super().__init__()
        self.workbook_path: Path | None = workbook_path

    def on_mount(self) -> None:
        self.push_screen(LauncherScreen())

    def action_quit(self) -> None:
        self.exit()
