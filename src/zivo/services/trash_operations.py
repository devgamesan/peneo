"""Service for trash lifecycle operations across supported platforms."""

import configparser
import platform
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from zivo.models import TrashRestoreRecord


class TrashService:
    """Boundary for trash operations."""

    def get_trash_path(self) -> str | None:
        """Return the trash directory path or None if not found."""

    def empty_trash(self) -> tuple[int, str]:
        """Empty trash and return (removed_count, error_message)."""

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        """Send an entry to trash and, when possible, capture restore metadata."""

    def restore(self, record: TrashRestoreRecord) -> str:
        """Restore a trashed entry back to its original path."""


@dataclass(frozen=True)
class LinuxTrashService:
    """Trash operations for Linux (freedesktop.org standard)."""

    def get_trash_path(self) -> str | None:
        trash_path = self._trash_root()
        return str(trash_path) if trash_path.exists() else None

    def empty_trash(self) -> tuple[int, str]:
        trash_path = self.get_trash_path()
        if not trash_path:
            return 0, "Trash directory not found"

        files_path = Path(trash_path) / "files"
        if not files_path.exists():
            return 0, "No items in trash"

        removed_count = 0
        failures = []

        try:
            for item in files_path.iterdir():
                try:
                    _remove_path(item)
                    removed_count += 1
                except OSError as error:
                    failures.append(f"{item.name}: {error}")

            info_path = Path(trash_path) / "info"
            if info_path.exists():
                for metadata_file in info_path.iterdir():
                    try:
                        metadata_file.unlink()
                    except OSError:
                        pass

            if failures:
                return removed_count, f"Removed {removed_count} items with {len(failures)} failures"
            return removed_count, ""
        except Exception as error:  # pragma: no cover - defensive fallback
            return 0, f"Failed to empty trash: {error}"

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        files_dir = self._trash_root() / "files"
        info_dir = self._trash_root() / "info"
        before_info = {item.name for item in info_dir.iterdir()} if info_dir.exists() else set()

        send_to_trash()

        if not info_dir.exists():
            return None

        resolved_original = str(Path(path).expanduser().resolve(strict=False))
        new_info_names = sorted({item.name for item in info_dir.iterdir()} - before_info)
        new_info_paths = [info_dir / name for name in new_info_names]
        matches: list[TrashRestoreRecord] = []
        for info_path in new_info_paths:
            original_path = _parse_trashinfo_original_path(info_path)
            if original_path != resolved_original:
                continue
            trashed_name = info_path.name.removesuffix(".trashinfo")
            trashed_path = files_dir / trashed_name
            if not trashed_path.exists():
                continue
            matches.append(
                TrashRestoreRecord(
                    original_path=original_path,
                    trashed_path=str(trashed_path),
                    metadata_path=str(info_path),
                )
            )

        if not matches:
            return None
        return max(matches, key=lambda record: Path(record.metadata_path).stat().st_mtime)

    def restore(self, record: TrashRestoreRecord) -> str:
        trashed_path = Path(record.trashed_path)
        metadata_path = Path(record.metadata_path)
        original_path = Path(record.original_path)
        if not trashed_path.exists():
            raise OSError(f"Trashed entry not found: {trashed_path.name}")
        if original_path.exists():
            raise OSError(f"Restore destination already exists: {original_path.name}")

        original_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(trashed_path), str(original_path))
        except OSError as error:
            raise OSError(str(error) or f"Failed to restore {original_path.name}") from error

        try:
            if metadata_path.exists():
                metadata_path.unlink()
        except OSError as error:
            raise OSError(str(error) or f"Failed to remove trash metadata for {original_path.name}")
        return str(original_path)

    @staticmethod
    def _trash_root() -> Path:
        return Path.home() / ".local/share/Trash"


@dataclass(frozen=True)
class MacOsTrashService:
    """Trash operations for macOS."""

    def get_trash_path(self) -> str | None:
        trash_path = Path.home() / ".Trash"
        return str(trash_path) if trash_path.exists() else None

    def empty_trash(self) -> tuple[int, str]:
        trash_path = self.get_trash_path()
        if not trash_path:
            return 0, "Trash directory not found"

        trash_dir = Path(trash_path)
        if not trash_dir.exists():
            return 0, "No items in trash"

        removed_count = 0
        failures = []

        try:
            for item in trash_dir.iterdir():
                try:
                    _remove_path(item)
                    removed_count += 1
                except OSError as error:
                    failures.append(f"{item.name}: {error}")

            if failures:
                return removed_count, f"Removed {removed_count} items with {len(failures)} failures"
            return removed_count, ""
        except Exception as error:  # pragma: no cover - defensive fallback
            return 0, f"Failed to empty trash: {error}"

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        # 1. 元のパス情報を収集
        original_path = str(Path(path).expanduser().resolve())
        original_name = Path(original_path).name

        # 2. ゴミ箱内の既存アイテムを確認
        trash_path = Path.home() / ".Trash"
        before_trash: set[str] = set()
        if trash_path.exists():
            try:
                before_trash = {item.name for item in trash_path.iterdir()}
            except PermissionError:
                pass

        # 3. ゴミ箱に移動実行
        send_to_trash()

        # 4. ゴミ箱内の新規アイテムを検出
        if not trash_path.exists():
            return None

        try:
            after_trash = {item.name for item in trash_path.iterdir()}
        except PermissionError:
            return None

        new_items = after_trash - before_trash

        # 5. 元ファイル名と一致するアイテムを探す
        candidates: list[Path] = []
        for item_name in new_items:
            if item_name == original_name or item_name.startswith(f"{original_name} "):
                trashed_path = trash_path / item_name
                if trashed_path.exists():
                    candidates.append(trashed_path)

        if not candidates:
            return None

        # 6. 最も新しいアイテムを選択（作成時間で判定）
        trashed_path = max(candidates, key=lambda p: p.stat().st_mtime)

        # 7. メタデータパスの生成（ダミーを使用）
        metadata_path = str(trashed_path) + ".zivorestore"

        return TrashRestoreRecord(
            original_path=original_path,
            trashed_path=str(trashed_path),
            metadata_path=metadata_path,
        )

    def restore(self, record: TrashRestoreRecord) -> str:
        trashed_path = Path(record.trashed_path)
        original_path = Path(record.original_path)

        if not trashed_path.exists():
            raise OSError(f"Trashed entry not found: {trashed_path.name}")
        if original_path.exists():
            raise OSError(f"Restore destination already exists: {original_path.name}")

        original_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(trashed_path), str(original_path))
        except OSError as error:
            raise OSError(str(error) or f"Failed to restore {original_path.name}") from error

        # メタデータのクリーンアップ
        metadata_path = Path(record.metadata_path)
        if metadata_path.exists() and metadata_path.name.endswith(".zivorestore"):
            try:
                metadata_path.unlink()
            except OSError:
                pass

        return str(original_path)


@dataclass(frozen=True)
class UnsupportedPlatformTrashService:
    """Placeholder for unsupported platforms."""

    def get_trash_path(self) -> str | None:
        return None

    def empty_trash(self) -> tuple[int, str]:
        return 0, "Empty trash is not supported on this platform"

    def capture_restorable_trash(
        self,
        path: str,
        send_to_trash: Callable[[], None],
    ) -> TrashRestoreRecord | None:
        send_to_trash()
        return None

    def restore(self, record: TrashRestoreRecord) -> str:
        raise OSError("Trash restore is not supported on this platform")


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def _parse_trashinfo_original_path(info_path: Path) -> str | None:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(info_path, encoding="utf-8")
    except (configparser.Error, OSError):
        return None
    if not parser.has_section("Trash Info"):
        return None
    encoded_path = parser.get("Trash Info", "Path", fallback=None)
    if encoded_path is None:
        return None
    return str(Path(unquote(encoded_path)).expanduser().resolve(strict=False))


def resolve_trash_service(
) -> LinuxTrashService | MacOsTrashService | UnsupportedPlatformTrashService:
    """Return appropriate trash service based on platform."""

    system = platform.system()
    if system == "Linux":
        return LinuxTrashService()
    if system == "Darwin":
        return MacOsTrashService()
    return UnsupportedPlatformTrashService()
