"""Command palette reducer handlers."""

from dataclasses import replace
from typing import Callable

from zivo.platform_support import is_split_terminal_supported
from zivo.windows_paths import is_search_workspace_path, list_windows_drive_paths

from .actions import (
    Action,
    AttributeInspectionFailed,
    AttributeInspectionLoaded,
    BeginBookmarkSearch,
    BeginCommandPalette,
    BeginFileSearch,
    BeginFindAndReplace,
    BeginGoToPath,
    BeginGrepExport,
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginSelectedFilesGrep,
    BeginTextReplace,
    CancelCommandPalette,
    CancelGrepExport,
    CycleFileSearchField,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    CycleSelectedFilesGrepField,
    DismissAboutDialog,
    DismissAttributeDialog,
    DismissHelpDialog,
    FileSearchCompleted,
    FileSearchFailed,
    GrepExportCompleted,
    GrepExportFailed,
    GrepSearchCompleted,
    GrepSearchFailed,
    MoveCommandPaletteCursor,
    OpenFindResultInEditor,
    OpenFindResultInGuiEditor,
    OpenGrepResultInEditor,
    OpenGrepResultInGuiEditor,
    SelectedFilesGrepKeywordChanged,
    SetCommandPaletteQuery,
    SetFileSearchTarget,
    SetFindReplaceField,
    SetGrepExportFilename,
    SetGrepExportFormat,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetReplaceField,
    ShowAbout,
    ShowAttributes,
    ShowHelp,
    SubmitCommandPalette,
    SubmitGrepExport,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
)
from .actions_palette import OpenSearchWorkspace
from .command_palette import normalize_command_palette_cursor
from .effects import ReduceResult
from .models import AppState, HelpDialogState, NotificationState
from .reducer_common import (
    ReducerFn,
    finalize,
    sync_child_pane,
)
from .reducer_palette_commands import (
    handle_show_attributes_command,
    handle_submit_commands_palette,
)
from .reducer_palette_export import (
    handle_begin_grep_export,
    handle_cancel_grep_export,
    handle_grep_export_completed,
    handle_grep_export_failed,
    handle_set_grep_export_filename,
    handle_set_grep_export_format,
    handle_submit_grep_export,
)
from .reducer_palette_navigation import (
    handle_begin_bookmark_search,
    handle_begin_go_to_path,
    handle_begin_history_search,
    handle_set_go_to_path_query,
    handle_submit_bookmarks_palette,
    handle_submit_go_to_path_palette,
    handle_submit_history_palette,
)
from .reducer_palette_replace import (
    handle_cycle_find_replace_field,
    handle_cycle_grep_replace_field,
    handle_cycle_grep_replace_selected_field,
    handle_cycle_replace_field,
    handle_set_find_replace_field,
    handle_set_grep_replace_field,
    handle_set_grep_replace_selected_field,
    handle_set_replace_field,
    handle_submit_find_and_replace_palette,
    handle_submit_grep_replace_palette,
    handle_submit_grep_replace_selected_palette,
    handle_submit_replace_palette,
    handle_text_replace_applied,
    handle_text_replace_apply_failed,
    handle_text_replace_preview_completed,
    handle_text_replace_preview_failed,
    sync_find_replace_preview,
    sync_grep_replace_preview,
    sync_grep_replace_selected_preview,
    sync_replace_preview,
)
from .reducer_palette_search import (
    handle_cycle_file_search_field,
    handle_cycle_sfg_field,
    handle_file_search_completed,
    handle_file_search_failed,
    handle_grep_search_completed,
    handle_grep_search_failed,
    handle_open_find_result_in_editor,
    handle_open_find_result_in_gui_editor,
    handle_open_grep_result_in_editor,
    handle_open_grep_result_in_gui_editor,
    handle_open_search_workspace,
    handle_set_file_search_query,
    handle_set_file_search_target,
    handle_set_grep_search_field,
    handle_sfg_keyword_changed,
    handle_submit_file_search_palette,
    handle_submit_grep_search_palette,
    sync_file_search_preview,
    sync_grep_preview,
    sync_sfg_preview,
)
from .reducer_palette_shared import (
    GREP_SEARCH_FIELDS,
    enter_palette,
    restore_browsing_from_palette,
)


def _handle_move_palette_cursor(state: AppState, action: MoveCommandPaletteCursor) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    next_palette = replace(
        state.command_palette,
        cursor_index=normalize_command_palette_cursor(
            state,
            state.command_palette.cursor_index + action.delta,
        ),
    )
    if state.command_palette.source == "go_to_path":
        next_palette = replace(
            next_palette,
            history_and_navigation=replace(
                next_palette.history_and_navigation,
                go_to_path_selection_active=True,
            ),
        )
    next_state = replace(state, command_palette=next_palette)
    if state.command_palette.source == "file_search":
        return sync_file_search_preview(next_state)
    if state.command_palette.source == "grep_search":
        return sync_grep_preview(next_state)
    if state.command_palette.source == "replace_text":
        return sync_replace_preview(next_state)
    if state.command_palette.source == "replace_in_found_files":
        return sync_find_replace_preview(next_state)
    if state.command_palette.source == "replace_in_grep_files":
        return sync_grep_replace_preview(next_state)
    if state.command_palette.source == "grep_replace_selected":
        return sync_grep_replace_selected_preview(next_state)
    if state.command_palette.source == "selected_files_grep":
        return sync_sfg_preview(next_state)
    return finalize(next_state)


def _next_palette_query_state(state: AppState, query: str):
    return replace(
        state.command_palette,
        query=query,
        cursor_index=0,
        file_search=replace(
            state.command_palette.file_search,
            error_message=None,
        ),
        grep_search=replace(
            state.command_palette.grep_search,
            error_message=None,
        ),
    )

def _handle_set_palette_query(state: AppState, action: SetCommandPaletteQuery) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    next_palette = _next_palette_query_state(state, action.query)
    if state.command_palette.source == "file_search":
        return handle_set_file_search_query(state, next_palette, action.query)
    if state.command_palette.source == "grep_search":
        return handle_set_grep_search_field(state, "keyword", action.query)
    if state.command_palette.source == "go_to_path":
        return handle_set_go_to_path_query(state, next_palette, action.query)
    if state.command_palette.source == "replace_in_grep_files":
        return handle_set_grep_replace_field(state, "keyword", action.query)
    if state.command_palette.source == "grep_replace_selected":
        return handle_set_grep_replace_selected_field(state, "keyword", action.query)
    if state.command_palette.source == "selected_files_grep":
        return handle_sfg_keyword_changed(
            state,
            SelectedFilesGrepKeywordChanged(keyword=action.query),
        )
    return finalize(replace(state, command_palette=next_palette))


def _handle_cycle_grep_search_field(state: AppState, action: CycleGrepSearchField) -> ReduceResult:
    if state.command_palette is None or state.command_palette.source != "grep_search":
        return finalize(state)
    current_index = GREP_SEARCH_FIELDS.index(state.command_palette.grep_search.active_field)
    next_index = (current_index + action.delta) % len(GREP_SEARCH_FIELDS)
    return finalize(
        replace(
            state,
            command_palette=replace(
                state.command_palette,
                grep_search=replace(
                    state.command_palette.grep_search,
                    active_field=GREP_SEARCH_FIELDS[next_index],
                ),
            ),
        )
    )

def _handle_submit_palette(state: AppState, reduce_state: ReducerFn) -> ReduceResult:
    if state.command_palette is None:
        return finalize(state)
    if state.command_palette.source == "file_search":
        return handle_submit_file_search_palette(state, reduce_state)
    if state.command_palette.source == "grep_search":
        return handle_submit_grep_search_palette(state, reduce_state)
    if state.command_palette.source == "replace_text":
        return handle_submit_replace_palette(state)
    if state.command_palette.source == "replace_in_found_files":
        return handle_submit_find_and_replace_palette(state)
    if state.command_palette.source == "replace_in_grep_files":
        return handle_submit_grep_replace_palette(state)
    if state.command_palette.source == "grep_replace_selected":
        return handle_submit_grep_replace_selected_palette(state)
    if state.command_palette.source == "selected_files_grep":
        return handle_submit_grep_search_palette(state, reduce_state)
    if state.command_palette.source == "history":
        return handle_submit_history_palette(state, reduce_state)
    if state.command_palette.source == "bookmarks":
        return handle_submit_bookmarks_palette(state, reduce_state)
    if state.command_palette.source == "go_to_path":
        return handle_submit_go_to_path_palette(state, reduce_state)
    return handle_submit_commands_palette(state, reduce_state)


def _handle_begin_command_palette(
    state: AppState,
    action: BeginCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state))


def _handle_begin_file_search(
    state: AppState,
    action: BeginFileSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="file_search"))


def _handle_begin_grep_search(
    state: AppState,
    action: BeginGrepSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="grep_search"))


def _handle_begin_text_replace(
    state: AppState,
    action: BeginTextReplace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    next_state = enter_palette(state, source="replace_text")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                replace_preview=replace(
                    next_state.command_palette.replace_preview,
                    target_paths=action.target_paths,
                ),
            ),
        )
    )


def _handle_begin_find_and_replace(
    state: AppState,
    action: BeginFindAndReplace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="replace_in_found_files"))


def _handle_begin_grep_replace(
    state: AppState,
    action: BeginGrepReplace,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(enter_palette(state, source="replace_in_grep_files"))


def _handle_begin_grep_replace_selected(
    state: AppState,
    action: BeginGrepReplaceSelected,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    next_state = enter_palette(state, source="grep_replace_selected")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                grs=replace(
                    next_state.command_palette.grs,
                    target_paths=action.target_paths,
                ),
            ),
        )
    )


def _handle_begin_selected_files_grep(
    state: AppState,
    action: BeginSelectedFilesGrep,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    next_state = enter_palette(state, source="selected_files_grep")
    return finalize(
        replace(
            next_state,
            command_palette=replace(
                next_state.command_palette,
                sfg=replace(
                    next_state.command_palette.sfg,
                    target_paths=action.target_paths,
                ),
            ),
        )
    )


def _dispatch_begin_history_search(
    state: AppState,
    action: BeginHistorySearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return handle_begin_history_search(state)


def _dispatch_begin_bookmark_search(
    state: AppState,
    action: BeginBookmarkSearch,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return handle_begin_bookmark_search(state)


def _handle_begin_go_to_path(
    state: AppState,
    action: BeginGoToPath,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return handle_begin_go_to_path(state, list_windows_drive_paths)


def _handle_cancel_command_palette(
    state: AppState,
    action: CancelCommandPalette,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action
    next_state = restore_browsing_from_palette(state, clear_name_conflict=True)
    if state.command_palette is not None and state.command_palette.source in {
        "file_search",
        "grep_search",
        "replace_text",
        "replace_in_found_files",
        "replace_in_grep_files",
        "grep_replace_selected",
        "selected_files_grep",
    }:
        return sync_child_pane(next_state, next_state.current_pane.cursor_path, reduce_state)
    return finalize(next_state)


def _handle_dismiss_about_dialog(
    state: AppState,
    action: DismissAboutDialog,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
        )
    )


def _handle_dismiss_help_dialog(
    state: AppState,
    action: DismissHelpDialog,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            help_dialog=None,
            notification=None,
        )
    )


def _help_dialog_for_state(state: AppState) -> HelpDialogState:
    if state.ui_mode == "PALETTE":
        return _palette_help_dialog(state)
    if state.layout_mode == "transfer":
        return HelpDialogState(
            title="Help: Transfer mode",
            lines=(
                "[ ] focus panes | j/k or arrows move | page/home/end jump",
                "space select | a select all | c copy | x cut | v paste",
                "y copy-to-pane | m move-to-pane | d trash | r rename | z undo",
                "b bookmarks | H history | G go to path | . hidden | : palette",
                "N new directory | o/w tabs | p or esc close transfer | q quit",
            ),
        )
    if is_search_workspace_path(state.current_path):
        return HelpDialogState(
            title="Help: Search workspace",
            lines=(
                "enter open | e editor | O GUI editor | i attributes",
                "j/k or arrows move | page/home/end jump | / filter | s sort",
                "space select | c copy | C copy path | . hidden | z undo",
                "[ back | ] forward | H history | b bookmarks | G go to path",
                ": palette | ? help | q quit",
            ),
        )
    split_terminal_hint = " | t terminal" if is_split_terminal_supported() else ""
    return HelpDialogState(
        title="Help: Browser",
        lines=(
            "enter open | h/l or arrows navigate | j/k or arrows move",
            "space select | a select all | c copy | x cut | v paste",
            "d trash | D permanent delete | r rename | n file | N directory",
            f"f find | g grep | / filter | s sort | . hidden{split_terminal_hint}",
            "e editor | O GUI editor | i attributes | C copy path | M file manager",
            "[ back | ] forward | H history | b bookmarks | B bookmark | G go to path",
            "o/w tabs | tab/shift+tab switch tabs | p transfer | : palette | ? help | q quit",
        ),
    )


def _palette_help_dialog(state: AppState) -> HelpDialogState:
    source = state.command_palette.source if state.command_palette is not None else "commands"
    source_titles = {
        "commands": "Command palette",
        "file_search": "File search",
        "grep_search": "Grep search",
        "history": "History search",
        "bookmarks": "Bookmarks",
        "go_to_path": "Go to path",
        "replace_text": "Replace text",
        "replace_in_found_files": "Find and replace",
        "replace_in_grep_files": "Grep and replace",
        "grep_replace_selected": "Grep and replace selected files",
        "selected_files_grep": "Selected-files grep",
    }
    if source == "go_to_path":
        lines = (
            "type path | tab complete selected candidate",
            "up/down or ctrl+j/k select | page/home/end jump",
            "enter jump | esc cancel | ? help",
        )
    elif source in {"file_search", "grep_search", "selected_files_grep"}:
        lines = (
            "type search text | up/down or ctrl+j/k select | page/home/end jump",
            "enter jump | ctrl+e editor | ctrl+o GUI editor",
            "ctrl+w workspace for file search | ctrl+x export grep results",
            "esc cancel | ? help",
        )
    elif source in {
        "replace_text",
        "replace_in_found_files",
        "replace_in_grep_files",
        "grep_replace_selected",
    }:
        lines = (
            "type values | tab/shift+tab switch fields",
            "up/down or ctrl+j/k select preview | page/home/end jump",
            "enter apply | ctrl+x export grep results where available",
            "esc cancel | ? help",
        )
    else:
        lines = (
            "type to filter commands | up/down or ctrl+j/k select",
            "page/home/end jump | enter run selected command",
            "shortcuts shown at right can also be used outside the palette",
            "esc cancel | ? help",
        )
    return HelpDialogState(
        title=f"Help: {source_titles.get(source, 'Palette')}",
        lines=lines,
    )


def _handle_show_help(
    state: AppState,
    action: ShowHelp,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(
        replace(
            state,
            ui_mode="HELP",
            notification=None,
            command_palette=None,
            help_dialog=_help_dialog_for_state(state),
        )
    )


def _handle_show_about(
    state: AppState,
    action: ShowAbout,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(
        replace(
            state,
            ui_mode="ABOUT",
            notification=None,
            command_palette=None,
        )
    )


def _handle_dismiss_attribute_dialog(
    state: AppState,
    action: DismissAttributeDialog,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return finalize(
        replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            attribute_inspection=None,
            pending_attribute_inspection_request_id=None,
        )
    )


def _handle_show_attributes(
    state: AppState,
    action: ShowAttributes,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del action, reduce_state
    return handle_show_attributes_command(state)


def _handle_attribute_inspection_loaded(
    state: AppState,
    action: AttributeInspectionLoaded,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_attribute_inspection_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=None,
            attribute_inspection=(
                action.inspection
                if state.attribute_inspection is not None
                else None
            ),
            pending_attribute_inspection_request_id=None,
        )
    )


def _handle_attribute_inspection_failed(
    state: AppState,
    action: AttributeInspectionFailed,
    reduce_state: ReducerFn,
) -> ReduceResult:
    del reduce_state
    if action.request_id != state.pending_attribute_inspection_request_id:
        return finalize(state)
    return finalize(
        replace(
            state,
            notification=NotificationState(level="error", message=action.message),
            pending_attribute_inspection_request_id=None,
        )
    )


_PaletteHandler = Callable[[AppState, Action, ReducerFn], ReduceResult]

_PALETTE_HANDLERS: dict[type[Action], _PaletteHandler] = {
    AttributeInspectionLoaded: _handle_attribute_inspection_loaded,
    AttributeInspectionFailed: _handle_attribute_inspection_failed,
    BeginCommandPalette: _handle_begin_command_palette,
    BeginFileSearch: _handle_begin_file_search,
    BeginGrepSearch: _handle_begin_grep_search,
    BeginTextReplace: _handle_begin_text_replace,
    BeginFindAndReplace: _handle_begin_find_and_replace,
    BeginGrepReplace: _handle_begin_grep_replace,
    BeginGrepReplaceSelected: _handle_begin_grep_replace_selected,
    BeginSelectedFilesGrep: _handle_begin_selected_files_grep,
    BeginHistorySearch: _dispatch_begin_history_search,
    BeginBookmarkSearch: _dispatch_begin_bookmark_search,
    BeginGoToPath: _handle_begin_go_to_path,
    CancelCommandPalette: _handle_cancel_command_palette,
    DismissAboutDialog: _handle_dismiss_about_dialog,
    DismissHelpDialog: _handle_dismiss_help_dialog,
    DismissAttributeDialog: _handle_dismiss_attribute_dialog,
    ShowAbout: _handle_show_about,
    ShowHelp: _handle_show_help,
    ShowAttributes: _handle_show_attributes,
    MoveCommandPaletteCursor: lambda s, a, r: _handle_move_palette_cursor(s, a),
    SetCommandPaletteQuery: lambda s, a, r: _handle_set_palette_query(s, a),
    SetGrepSearchField: lambda s, a, r: handle_set_grep_search_field(s, a.field, a.value),
    SetReplaceField: lambda s, a, r: handle_set_replace_field(s, a.field, a.value),
    CycleGrepSearchField: lambda s, a, r: _handle_cycle_grep_search_field(s, a),
    CycleReplaceField: lambda s, a, r: handle_cycle_replace_field(s, a),
    SetFindReplaceField: lambda s, a, r: handle_set_find_replace_field(s, a.field, a.value),
    CycleFindReplaceField: lambda s, a, r: handle_cycle_find_replace_field(s, a),
    SetGrepReplaceField: lambda s, a, r: handle_set_grep_replace_field(s, a.field, a.value),
    SetGrepReplaceSelectedField: lambda s, a, r: handle_set_grep_replace_selected_field(
        s,
        a.field,
        a.value,
    ),
    SelectedFilesGrepKeywordChanged: lambda s, a, r: handle_sfg_keyword_changed(s, a),
    CycleGrepReplaceField: lambda s, a, r: handle_cycle_grep_replace_field(s, a),
    CycleGrepReplaceSelectedField: lambda s, a, r: handle_cycle_grep_replace_selected_field(s, a),
    CycleSelectedFilesGrepField: lambda s, a, r: handle_cycle_sfg_field(s, a),
    SetFileSearchTarget: lambda s, a, r: handle_set_file_search_target(s, a),
    CycleFileSearchField: lambda s, a, r: handle_cycle_file_search_field(s, a),
    SubmitCommandPalette: lambda s, a, r: _handle_submit_palette(s, r),
    FileSearchCompleted: lambda s, a, r: handle_file_search_completed(s, a),
    FileSearchFailed: lambda s, a, r: handle_file_search_failed(s, a),
    GrepSearchCompleted: lambda s, a, r: handle_grep_search_completed(s, a),
    GrepSearchFailed: lambda s, a, r: handle_grep_search_failed(s, a),
    TextReplacePreviewCompleted: lambda s, a, r: handle_text_replace_preview_completed(s, a),
    TextReplacePreviewFailed: lambda s, a, r: handle_text_replace_preview_failed(s, a),
    TextReplaceApplied: lambda s, a, r: handle_text_replace_applied(s, a, r),
    TextReplaceApplyFailed: lambda s, a, r: handle_text_replace_apply_failed(s, a),
    OpenGrepResultInEditor: lambda s, a, r: handle_open_grep_result_in_editor(s, r),
    OpenFindResultInEditor: lambda s, a, r: handle_open_find_result_in_editor(s, r),
    OpenGrepResultInGuiEditor: lambda s, a, r: handle_open_grep_result_in_gui_editor(s, r),
    OpenFindResultInGuiEditor: lambda s, a, r: handle_open_find_result_in_gui_editor(s, r),
    OpenSearchWorkspace: lambda s, a, r: handle_open_search_workspace(s, a, r),
    BeginGrepExport: lambda s, a, r: handle_begin_grep_export(s, a),
    CancelGrepExport: lambda s, a, r: handle_cancel_grep_export(s, a),
    SetGrepExportFormat: lambda s, a, r: handle_set_grep_export_format(s, a),
    SetGrepExportFilename: lambda s, a, r: handle_set_grep_export_filename(s, a),
    SubmitGrepExport: lambda s, a, r: handle_submit_grep_export(s, a),
    GrepExportCompleted: lambda s, a, r: handle_grep_export_completed(s, a),
    GrepExportFailed: lambda s, a, r: handle_grep_export_failed(s, a),
}


def handle_palette_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    handler = _PALETTE_HANDLERS.get(type(action))
    if handler is not None:
        return handler(state, action, reduce_state)  # type: ignore[arg-type]
    return None
