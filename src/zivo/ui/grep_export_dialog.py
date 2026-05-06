"""Overlay dialog for grep export options."""

from rich.text import Text
from textual.containers import Container
from textual.widgets import Static

from zivo.models.shell_data import GrepExportDialogViewState, GrepExportFormat

_FORMAT_LABELS: dict[GrepExportFormat, str] = {
    "single_line": "Single Line",
    "context": "Context",
    "json": "JSON",
}

_FORMAT_CYCLE: tuple[GrepExportFormat, ...] = ("single_line", "context", "json")


class GrepExportDialog(Container):
    """Overlay dialog for grep export filename and format selection."""

    def __init__(
        self,
        state: GrepExportDialogViewState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.state = state

    def compose(self):
        yield Static("", id="grep-export-dialog-title")
        yield Static("", id="grep-export-dialog-filename")
        yield Static("", id="grep-export-dialog-format")
        yield Static("", id="grep-export-dialog-options")

    def on_mount(self) -> None:
        self.set_state(self.state)

    def set_state(self, state: GrepExportDialogViewState | None) -> None:
        self.state = state
        self.display = state is not None
        if state is None:
            self.query_one("#grep-export-dialog-title", Static).update("")
            self.query_one("#grep-export-dialog-filename", Static).update("")
            self.query_one("#grep-export-dialog-format", Static).update("")
            self.query_one("#grep-export-dialog-options", Static).update("")
            return

        self.query_one("#grep-export-dialog-title", Static).update("Export Grep Results")
        self.query_one("#grep-export-dialog-filename", Static).update(
            self._render_filename_input(state.filename, state.cursor_pos)
        )
        self.query_one("#grep-export-dialog-format", Static).update(
            self._render_format_row(state.format)
        )
        self.query_one("#grep-export-dialog-options", Static).update(
            "[Enter] Export  [Esc] Cancel"
        )

    @staticmethod
    def _render_filename_input(filename: str, cursor_pos: int) -> Text:
        text = Text("Filename: ", style="bold")
        if not filename:
            text.append("_", style="reverse")
            return text
        before = filename[:cursor_pos]
        at_cursor = filename[cursor_pos] if cursor_pos < len(filename) else None
        after = filename[cursor_pos + 1 :]
        text.append(before, style="underline")
        if at_cursor is not None:
            text.append(at_cursor, style="reverse underline")
            text.append(after, style="underline")
        else:
            text.append("_", style="reverse")
        return text

    @staticmethod
    def _render_format_row(current_format: GrepExportFormat) -> Text:
        text = Text("Format [f]: ", style="bold")
        for fmt in _FORMAT_CYCLE:
            if fmt == current_format:
                text.append(f"[{_FORMAT_LABELS[fmt]}] ", style="reverse")
            else:
                text.append(f" {_FORMAT_LABELS[fmt]}  ")
        return text
