"""Empty trash service using OS standard CLI."""

import subprocess
from dataclasses import dataclass
from typing import Protocol

from peneo.models.file_operations import MutationResultLevel


@dataclass(frozen=True)
class EmptyTrashResult:
    """Result of emptying trash."""

    message: str
    level: MutationResultLevel = "info"


class EmptyTrashService(Protocol):
    """Boundary for emptying trash operations."""

    def execute(self) -> EmptyTrashResult: ...


@dataclass(frozen=True)
class LiveEmptyTrashService:
    """Execute trash emptying using OS standard CLI."""

    def execute(self) -> EmptyTrashResult:
        # 1. gio を優先
        try:
            result = subprocess.run(
                ["gio", "trash", "--empty"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return EmptyTrashResult(message="Trash emptied successfully")
        except FileNotFoundError:
            pass

        # 2. trash-cli をフォールバック
        try:
            result = subprocess.run(
                ["trash-empty"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return EmptyTrashResult(message="Trash emptied successfully")
        except FileNotFoundError:
            pass

        # 3. エラー
        return EmptyTrashResult(
            message="No trash utility found. Please install gio or trash-cli.",
            level="error",
        )
