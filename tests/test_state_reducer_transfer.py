from tests.test_state_reducer import _reduce_state
from zivo.models import PasteRequest
from zivo.state import (
    LoadTransferPaneEffect,
    RunClipboardPasteEffect,
    build_initial_app_state,
    reduce_app_state,
    select_shell_data,
)
from zivo.state.actions import (
    EnterTransferDirectory,
    FocusTransferPane,
    ToggleTransferMode,
    TransferCopyToOppositePane,
    TransferMoveToOppositePane,
)


def test_toggle_transfer_mode_initializes_left_and_right_from_current_pane() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    assert state.layout_mode == "transfer"
    assert state.active_transfer_pane == "left"
    assert state.transfer_left is not None
    assert state.transfer_right is not None
    assert state.transfer_left.current_path == state.current_path
    assert state.transfer_right.current_path == state.current_path
    assert state.transfer_left.pane == state.current_pane
    assert state.transfer_right.pane == state.current_pane


def test_transfer_copy_to_opposite_pane_uses_paste_effect() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    reduced = reduce_app_state(state, TransferCopyToOppositePane())

    assert reduced.state.ui_mode == "BUSY"
    assert reduced.effects == (
        RunClipboardPasteEffect(
            request_id=1,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
        ),
    )


def test_transfer_move_to_opposite_pane_uses_cut_paste_request() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    reduced = reduce_app_state(state, TransferMoveToOppositePane())

    assert reduced.effects == (
        RunClipboardPasteEffect(
            request_id=1,
            request=PasteRequest(
                mode="cut",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
        ),
    )


def test_enter_transfer_directory_loads_active_pane_snapshot() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    reduced = reduce_app_state(state, EnterTransferDirectory())

    effect = reduced.effects[0]
    assert isinstance(effect, LoadTransferPaneEffect)
    assert effect.request_id == 1
    assert effect.pane_id == "left"
    assert effect.path == "/home/tadashi/develop/zivo/docs"
    assert effect.invalidate_paths[0].endswith("/home/tadashi/develop/zivo/docs")
    assert effect.invalidate_paths[1].endswith("/home/tadashi/develop/zivo")


def test_focus_transfer_pane_changes_active_side() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    next_state = _reduce_state(state, FocusTransferPane("right"))

    assert next_state.active_transfer_pane == "right"


def test_select_shell_data_exposes_transfer_panes() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    shell = select_shell_data(state)

    assert shell.layout_mode == "transfer"
    assert shell.transfer_left is not None
    assert shell.transfer_right is not None
    assert shell.transfer_left.active is True
    assert shell.transfer_right.active is False
    assert shell.transfer_left.entries[0].name == "docs"
    assert shell.transfer_right.entries[0].name == "docs"
