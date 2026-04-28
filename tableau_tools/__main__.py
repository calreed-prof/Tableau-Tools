"""Interactive launcher for the Tableau Tools package.

Run with:
    python -m tableau_tools
"""

from __future__ import annotations

import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

from . import calculated_fields, sql_editor
from .common import validate_workbook_path

console = Console()


def _pick_workbook() -> Path | None:
    """Open a native file dialog filtered to .twb / .twbx workbooks.

    Falls back to a typed prompt if tkinter is unavailable (e.g. headless
    Linux without python3-tk installed). Returns None if the user cancels.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        console.print("[yellow]tkinter not available — type the path instead.[/]")
        raw = input("  Workbook path: ").strip().strip('"').strip("'")
        if not raw:
            return None
        return validate_workbook_path(raw)

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    chosen = filedialog.askopenfilename(
        title="Select a Tableau workbook",
        filetypes=[
            ("Tableau workbooks", "*.twb *.twbx"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()

    if not chosen:
        return None
    return validate_workbook_path(chosen)


def _launch_sql_editor() -> None:
    path = _pick_workbook()
    if path is None:
        return
    sql_editor.run(path)


def _launch_calculated_fields() -> None:
    path = _pick_workbook()
    if path is None:
        return
    fmt = questionary.select(
        "Output format:",
        choices=["stdout", "csv"],
        default="stdout",
    ).ask()
    if fmt is None:
        return
    calculated_fields.run(path, fmt=fmt)


TOOLS = [
    ("Edit SQL",         "Initial / Custom SQL", _launch_sql_editor),
    ("List calc fields", "name + formula",       _launch_calculated_fields),
]


def main() -> None:
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Tableau Tools[/]\n[dim]Edit and inspect Tableau workbooks — press Ctrl+C to exit[/]",
            border_style="cyan",
        )
    )

    choices = [
        questionary.Choice(f"{name:<18} — {desc}", value=fn)
        for name, desc, fn in TOOLS
    ]

    try:
        while True:
            console.print()
            chosen = questionary.select("Choose a tool:", choices=choices).ask()
            if chosen is None:
                break
            chosen()
    except KeyboardInterrupt:
        pass

    console.print("\n[dim]Goodbye.[/]\n")


if __name__ == "__main__":
    main()
