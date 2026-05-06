"""Tests for the grep export reducer handlers."""

from dataclasses import replace

from zivo.state import (
    AppState,
    GrepExportDialogState,
    GrepSearchResultState,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import (
    BeginGrepExport,
    CancelGrepExport,
    GrepExportCompleted,
    GrepExportFailed,
    SetGrepExportFilename,
    SetGrepExportFormat,
    SubmitGrepExport,
)
from zivo.state.effects import RunGrepExportEffect


def _state_with_grep_results() -> AppState:
    """Return an AppState in PALETTE mode with grep search results."""
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="PALETTE",
        command_palette=replace(
            state.command_palette or _default_palette(),
            source="grep_search",
            grep_search=replace(
                state.command_palette.grep_search if state.command_palette
                else _default_palette().grep_search,
                keyword="hello",
                results=(
                    GrepSearchResultState(
                        path="/root/src/main.py",
                        display_path="src/main.py",
                        line_number=10,
                        line_text="def hello():",
                    ),
                ),
            ),
        ),
    )
    return state


def _default_palette():
    from zivo.state.models import CommandPaletteState
    return CommandPaletteState()


class TestBeginGrepExport:
    def test_transitions_to_grep_export_mode(self) -> None:
        state = _state_with_grep_results()
        result = reduce_app_state(state, BeginGrepExport())
        assert result.state.ui_mode == "GREP_EXPORT"
        assert result.state.grep_export_dialog is not None
        assert result.state.grep_export_dialog.format == "single_line"

    def test_ignores_when_no_palette(self) -> None:
        state = build_initial_app_state()
        result = reduce_app_state(state, BeginGrepExport())
        assert result.state.ui_mode == "BROWSING"
        assert result.state.grep_export_dialog is None

    def test_warns_when_no_results(self) -> None:
        from zivo.state.models import CommandPaletteState
        state = replace(
            build_initial_app_state(),
            ui_mode="PALETTE",
            command_palette=CommandPaletteState(
                source="grep_search",
                grep_search=replace(
                    build_initial_app_state().command_palette.grep_search
                    if build_initial_app_state().command_palette
                    else CommandPaletteState().grep_search,
                    keyword="hello",
                ),
            ),
        )
        result = reduce_app_state(state, BeginGrepExport())
        assert result.state.notification is not None
        assert result.state.notification.level == "warning"
        assert "No grep results" in result.state.notification.message


class TestCancelGrepExport:
    def test_returns_to_palette(self) -> None:
        state = replace(
            _state_with_grep_results(),
            ui_mode="GREP_EXPORT",
            grep_export_dialog=GrepExportDialogState(),
        )
        result = reduce_app_state(state, CancelGrepExport())
        assert result.state.grep_export_dialog is None
        assert result.state.ui_mode == "PALETTE"


class TestSetGrepExportFormat:
    def test_updates_format(self) -> None:
        state = replace(
            _state_with_grep_results(),
            ui_mode="GREP_EXPORT",
            grep_export_dialog=GrepExportDialogState(),
        )
        result = reduce_app_state(state, SetGrepExportFormat("json"))
        assert result.state.grep_export_dialog is not None
        assert result.state.grep_export_dialog.format == "json"

    def test_ignores_when_no_dialog(self) -> None:
        state = build_initial_app_state()
        result = reduce_app_state(state, SetGrepExportFormat("json"))
        assert result.state.grep_export_dialog is None


class TestSetGrepExportFilename:
    def test_updates_filename_and_cursor(self) -> None:
        state = replace(
            _state_with_grep_results(),
            ui_mode="GREP_EXPORT",
            grep_export_dialog=GrepExportDialogState(),
        )
        result = reduce_app_state(state, SetGrepExportFilename("output.txt", 5))
        assert result.state.grep_export_dialog is not None
        assert result.state.grep_export_dialog.filename == "output.txt"
        assert result.state.grep_export_dialog.cursor_pos == 5


class TestSubmitGrepExport:
    def test_emits_effect(self) -> None:
        state = replace(
            _state_with_grep_results(),
            ui_mode="GREP_EXPORT",
            grep_export_dialog=GrepExportDialogState(
                filename="out.txt",
                format="single_line",
                context_lines=3,
            ),
        )
        result = reduce_app_state(state, SubmitGrepExport())
        assert len(result.effects) == 1
        effect = result.effects[0]
        assert isinstance(effect, RunGrepExportEffect)
        assert effect.format == "single_line"
        assert effect.context_lines == 3
        assert effect.output_path.endswith("out.txt")
        assert len(effect.results) == 1
        assert effect.search_query == "hello"

    def test_rejects_empty_filename(self) -> None:
        state = replace(
            _state_with_grep_results(),
            ui_mode="GREP_EXPORT",
            grep_export_dialog=GrepExportDialogState(filename=""),
        )
        result = reduce_app_state(state, SubmitGrepExport())
        assert len(result.effects) == 0
        assert result.state.notification is not None
        assert "cannot be empty" in result.state.notification.message.lower()

    def test_ignores_when_no_dialog(self) -> None:
        state = build_initial_app_state()
        result = reduce_app_state(state, SubmitGrepExport())
        assert len(result.effects) == 0

    def test_warns_when_file_exists(self) -> None:
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            existing = tmp + "/out.txt"
            open(existing, "w").close()
            state = replace(
                _state_with_grep_results(),
                current_path=tmp,
                ui_mode="GREP_EXPORT",
                grep_export_dialog=GrepExportDialogState(
                    filename="out.txt",
                    format="single_line",
                    context_lines=3,
                ),
            )
            result = reduce_app_state(state, SubmitGrepExport())
            assert len(result.effects) == 0
            assert result.state.notification is not None
            assert "already exists" in result.state.notification.message.lower()
        finally:
            shutil.rmtree(tmp)


class TestGrepExportCompleted:
    def test_shows_success_notification(self) -> None:
        state = replace(
            build_initial_app_state(),
            pending_grep_export_request_id=42,
        )
        result = reduce_app_state(
            state,
            GrepExportCompleted(request_id=42, destination_path="/tmp/out.txt", exported_results=3),
        )
        assert result.state.pending_grep_export_request_id is None
        assert result.state.notification is not None
        assert result.state.notification.level == "info"
        assert "Exported 3 results" in result.state.notification.message

    def test_ignores_mismatched_request_id(self) -> None:
        state = replace(
            build_initial_app_state(),
            pending_grep_export_request_id=1,
        )
        result = reduce_app_state(
            state,
            GrepExportCompleted(request_id=99, destination_path="/tmp/out.txt", exported_results=3),
        )
        assert result.state.pending_grep_export_request_id == 1


class TestGrepExportFailed:
    def test_shows_error_notification(self) -> None:
        state = replace(
            build_initial_app_state(),
            pending_grep_export_request_id=42,
        )
        result = reduce_app_state(
            state,
            GrepExportFailed(request_id=42, message="Permission denied"),
        )
        assert result.state.pending_grep_export_request_id is None
        assert result.state.notification is not None
        assert result.state.notification.level == "error"
        assert "Permission denied" in result.state.notification.message
