"""Split-terminal widget."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from peneo.models import SplitTerminalViewState


class SplitTerminalPane(Static):
    """Embedded split-terminal output pane."""

    DEFAULT_STATE = SplitTerminalViewState(
        visible=False,
        title="Split Terminal",
        status="closed",
        body="",
        focused=False,
    )

    def __init__(
        self,
        state: SplitTerminalViewState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.can_focus = True
        self.state = state

    def compose(self) -> ComposeResult:
        yield Static("", id="split-terminal-title")
        yield Static("", id="split-terminal-status")
        with VerticalScroll(id="split-terminal-scroll"):
            yield Static("", id="split-terminal-body")

    def on_mount(self) -> None:
        self.set_state(self.state)

    def set_state(self, state: SplitTerminalViewState) -> None:
        """Update visibility and rendered terminal content."""

        self.state = state
        self.display = state.visible
        self.set_class(state.visible, "-visible")
        self.set_class(state.focused, "-focused")

        title = self.query_one("#split-terminal-title", Static)
        status = self.query_one("#split-terminal-status", Static)
        body = self.query_one("#split-terminal-body", Static)
        scroll = self.query_one("#split-terminal-scroll", VerticalScroll)

        title.update(state.title)
        status.update(f"Status: {state.status}")
        body.update(Text.from_ansi(state.body or ""))
        if state.visible:
            self.call_after_refresh(
                scroll.scroll_end,
                animate=False,
                force=True,
                immediate=True,
                x_axis=False,
            )
