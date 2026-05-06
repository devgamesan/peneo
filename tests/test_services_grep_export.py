"""Tests for the grep export service."""

import json
from pathlib import Path

import pytest

from zivo.services.grep_export import FakeGrepExportService, LiveGrepExportService
from zivo.state.models import GrepSearchResultState


def _make_results(*items: tuple[str, int, str]) -> tuple[GrepSearchResultState, ...]:
    return tuple(
        GrepSearchResultState(
            path=f"/root/{path}",
            display_path=path,
            line_number=line,
            line_text=text,
        )
        for path, line, text in items
    )


_RESULTS = _make_results(
    ("src/main.py", 10, "def hello():"),
    ("src/main.py", 42, "    return result"),
    ("README.md", 5, "# Project"),
)


class TestFakeGrepExportService:
    def test_export_records_call(self) -> None:
        service = FakeGrepExportService()
        result = service.export(
            output_path="/tmp/out.txt",
            format="single_line",
            context_lines=3,
            results=_RESULTS,
            search_query="hello",
        )
        assert result == "/tmp/out.txt"
        assert len(service.exported) == 1
        assert service.exported[0]["output_path"] == "/tmp/out.txt"
        assert service.exported[0]["format"] == "single_line"
        assert service.exported[0]["result_count"] == 3
        assert service.exported[0]["search_query"] == "hello"

    def test_export_failure(self) -> None:
        service = FakeGrepExportService(failure_message="Disk full")
        with pytest.raises(OSError, match="Disk full"):
            service.export(
                output_path="/tmp/out.txt",
                format="single_line",
                context_lines=3,
                results=_RESULTS,
            )

    def test_export_empty_results(self) -> None:
        service = FakeGrepExportService()
        result = service.export(
            output_path="/tmp/out.txt",
            format="single_line",
            context_lines=3,
            results=(),
        )
        assert result == "/tmp/out.txt"


class TestLiveGrepExportServiceSingleLine:
    def test_basic(self, tmp_path: Path) -> None:
        output = tmp_path / "out.txt"
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="single_line",
            context_lines=3,
            results=_RESULTS,
        )
        content = output.read_text()
        assert "src/main.py:10: def hello():" in content
        assert "src/main.py:42:     return result" in content
        assert "README.md:5: # Project" in content

    def test_empty_results(self, tmp_path: Path) -> None:
        output = tmp_path / "out.txt"
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="single_line",
            context_lines=3,
            results=(),
        )
        assert output.read_text() == ""

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        output = tmp_path / "sub" / "deep" / "out.txt"
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="single_line",
            context_lines=3,
            results=_RESULTS,
        )
        assert output.exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        output = tmp_path / "out.txt"
        output.write_text("existing content")
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="single_line",
            context_lines=3,
            results=_RESULTS,
        )
        assert output.read_text().startswith("src/main.py:")


class TestLiveGrepExportServiceContext:
    def test_with_context_lines(self, tmp_path: Path) -> None:
        source = tmp_path / "src" / "main.py"
        source.parent.mkdir(parents=True)
        source.write_text("line1\nline2\nline3\nline4\nline5\nline6\nline7\n")
        results = (
            GrepSearchResultState(
                path=str(source),
                display_path="src/main.py",
                line_number=4,
                line_text="line4",
            ),
        )
        output = tmp_path / "out.txt"
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="context",
            context_lines=1,
            results=results,
        )
        content = output.read_text()
        assert "src/main.py:4: line4" in content
        assert "3: line3" in content
        assert "5: line5" in content

    def test_context_empty_results(self, tmp_path: Path) -> None:
        output = tmp_path / "out.txt"
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="context",
            context_lines=3,
            results=(),
        )
        assert output.read_text() == ""

    def test_context_missing_source_file(self, tmp_path: Path) -> None:
        results = _make_results(("nonexistent.py", 1, "content"))
        output = tmp_path / "out.txt"
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="context",
            context_lines=3,
            results=results,
        )
        content = output.read_text()
        assert "nonexistent.py:1: content" in content


class TestLiveGrepExportServiceJson:
    def test_basic_json(self, tmp_path: Path) -> None:
        output = tmp_path / "out.json"
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="json",
            context_lines=3,
            results=_RESULTS,
            search_query="hello",
        )
        data = json.loads(output.read_text())
        assert data["query"] == "hello"
        assert data["total_results"] == 3
        assert data["context_lines"] == 3
        assert "exported_at" in data
        assert len(data["results"]) == 3
        assert data["results"][0]["display_path"] == "src/main.py"
        assert data["results"][0]["line_number"] == 10
        assert data["results"][0]["text"] == "def hello():"

    def test_json_empty_results(self, tmp_path: Path) -> None:
        output = tmp_path / "out.json"
        service = LiveGrepExportService()
        service.export(
            output_path=str(output),
            format="json",
            context_lines=3,
            results=(),
            search_query="",
        )
        data = json.loads(output.read_text())
        assert data["total_results"] == 0
        assert data["results"] == []


class TestLiveGrepExportServiceProgress:
    def test_progress_callback_called(self, tmp_path: Path) -> None:
        output = tmp_path / "out.txt"
        service = LiveGrepExportService()
        calls: list[tuple[int, int]] = []

        def progress(current: int, total: int) -> None:
            calls.append((current, total))

        service.export(
            output_path=str(output),
            format="single_line",
            context_lines=3,
            results=_RESULTS,
            progress_callback=progress,
        )
        assert len(calls) == 1
        assert calls[0] == (3, 3)
