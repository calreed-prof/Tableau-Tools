"""Modal screen for picking a .twb / .twbx workbook."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Footer, Input, Static


class _WorkbookTree(DirectoryTree):
    """DirectoryTree filtered to directories + Tableau workbook files."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        for p in paths:
            if p.name.startswith("."):
                continue
            if p.is_dir() or p.suffix.lower() in (".twb", ".twbx"):
                yield p


class WorkbookPickerScreen(ModalScreen[Path | None]):
    """Pick a workbook from disk. Dismisses with the chosen Path or None."""

    CSS = """
    WorkbookPickerScreen {
        align: center middle;
    }
    #picker-box {
        width: 90%;
        height: 90%;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }
    #picker-title { padding-bottom: 0; color: $accent; text-style: bold; }
    #picker-root  { padding-bottom: 1; color: $text-muted; }
    #picker-tree  { height: 1fr; border: round $primary 50%; }
    #picker-row   { height: auto; padding-top: 1; }
    #picker-row Input  { width: 1fr; }
    #picker-row Button { margin-left: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("u", "parent", "Up a folder"),
        Binding("backspace", "parent", "Up", show=False),
        Binding("ctrl+l", "focus_input", "Type path", show=False),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, start: Path | None = None) -> None:
        super().__init__()
        self._start = (start or Path.cwd()).resolve()

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Static("Select a Tableau workbook (.twb / .twbx)", id="picker-title")
            yield Static(f"📁 {self._start}", id="picker-root")
            yield _WorkbookTree(str(self._start), id="picker-tree")
            with Horizontal(id="picker-row"):
                yield Input(placeholder="…or paste an absolute path (Enter to open)", id="picker-input")
                yield Button("↑ Parent", id="picker-up")
                yield Button("Open", variant="primary", id="picker-open")
                yield Button("Cancel", id="picker-cancel")
            yield Footer()

    # ---------------------------------------------------------------- events

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        if path.suffix.lower() in (".twb", ".twbx"):
            self.dismiss(path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._open_typed(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-open":
            self._open_typed(self.query_one("#picker-input", Input).value)
        elif event.button.id == "picker-up":
            self.action_parent()
        elif event.button.id == "picker-cancel":
            self.dismiss(None)

    # --------------------------------------------------------------- actions

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_focus_input(self) -> None:
        self.query_one("#picker-input", Input).focus()

    def action_parent(self) -> None:
        tree = self.query_one("#picker-tree", _WorkbookTree)
        current = Path(tree.path).resolve()
        parent = current.parent
        if parent == current:
            self.app.notify("Already at the filesystem root.", severity="warning")
            return
        self._reroot(parent)

    def _reroot(self, new_root: Path) -> None:
        tree = self.query_one("#picker-tree", _WorkbookTree)
        tree.path = new_root
        self.query_one("#picker-root", Static).update(f"📁 {new_root}")
        tree.focus()

    # ----------------------------------------------------------- typed paths

    def _open_typed(self, raw: str) -> None:
        raw = raw.strip().strip('"').strip("'")
        if not raw:
            return
        p = Path(raw).expanduser()
        if not p.exists():
            self.app.notify(f"Not found: {p}", severity="error")
            return
        # If they typed a directory, re-root the tree there instead of erroring.
        if p.is_dir():
            self._reroot(p.resolve())
            self.query_one("#picker-input", Input).value = ""
            return
        if p.suffix.lower() not in (".twb", ".twbx"):
            self.app.notify("Must be a .twb or .twbx", severity="error")
            return
        self.dismiss(p)
