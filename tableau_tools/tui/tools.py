"""Registry of tools shown in the main TUI launcher.

To add a new tool:
  1. Build a Screen subclass (see docs/adding_tools.md).
  2. Append (label, description, ScreenClass) below.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, NamedTuple

from textual.screen import Screen

from .screens.calculated_fields_screen import CalculatedFieldsScreen
from .screens.sql_editor_screen import SqlEditorScreen


class ToolEntry(NamedTuple):
    label: str
    description: str
    screen_factory: Callable[[Path], Screen]


TOOLS: list[ToolEntry] = [
    ToolEntry("Edit SQL",         "Initial / Custom SQL / Published DS",   SqlEditorScreen),
    ToolEntry("List calc fields", "Calculated fields (export to CSV)",     CalculatedFieldsScreen),
]
