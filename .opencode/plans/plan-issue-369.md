## Plan for Issue #369

### 1. 目的
Split terminal 内で `Tab` キーを押したときに、タブ補完文字 (`\t`) が PTY セッションに送信されるようにする。

### 2. 現状の問題
- `src/peneo/state/input.py:145-160` の `TERMINAL_KEYMAP` に `"tab"` が定義されていない
- `src/peneo/state/input.py:420-421` に `terminal_tab` を `\t` として送信する分岐は存在するが、keymap 未定義のため到達不能
- `Tab` キーがアプリ共通のキーディスパッチ経路を通らず、Textual の標準フォーカス移動に流れている

### 3. 実装方針

#### 3.1 コード変更
**ファイル:** `src/peneo/state/input.py`

1. `TERMINAL_KEYMAP` に `"tab": "terminal_tab"` を追加

#### 3.2 テスト追加
**ファイル:** `tests/test_app.py`

2. Split terminal 内で `Tab` キーを押したときに `\t` が送信されることを確認するテストを追加

**ファイル:** `tests/test_input_dispatch.py`

3. `_dispatch_terminal_input` で `tab` キーが `SendSplitTerminalInput("\t")` を返すことを確認するテストを追加

### 4. ベースブランチ
`develop`
