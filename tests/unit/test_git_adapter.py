from __future__ import annotations

from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess
from unittest.mock import MagicMock, call, patch

import pytest

from hsm_sync.adapters.git_adapter import GitAdapter, _parse_name_status
from hsm_sync.core.models import FileChange

FAKE_REPO = Path("/fake/repo")


def _completed(stdout="", returncode=0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestParseNameStatus:
    def test_mixed_statuses(self):
        output = "M\tindex.php\nA\tnewfile.js\nD\told.css"
        result = _parse_name_status(output)
        assert result == [
            FileChange(path="index.php", status="M"),
            FileChange(path="newfile.js", status="A"),
            FileChange(path="old.css", status="D"),
        ]

    def test_empty_output_returns_empty_list(self):
        assert _parse_name_status("") == []

    def test_rename_line(self):
        result = _parse_name_status("R100\told.php\tnew.php")
        assert result == [FileChange(path="new.php", status="R")]


class TestGitAdapterCommit:
    @patch("hsm_sync.adapters.git_adapter.subprocess.run")
    def test_commit_runs_add_then_commit(self, mock_run):
        mock_run.return_value = _completed()
        adapter = GitAdapter(FAKE_REPO)
        adapter.commit("sync: 2026-01-01")

        assert mock_run.call_count == 2
        first_args = mock_run.call_args_list[0][0][0]
        second_args = mock_run.call_args_list[1][0][0]
        assert first_args == ["git", "-C", str(FAKE_REPO), "add", "-A"]
        assert "--allow-empty" in second_args
        assert "sync: 2026-01-01" in second_args


class TestGitAdapterGetChangedFiles:
    @patch("hsm_sync.adapters.git_adapter.subprocess.run")
    def test_normal_diff(self, mock_run):
        mock_run.side_effect = [
            _completed("3\n"),  # rev-list count
            _completed("M\tindex.php\nA\tnewfile.js\nD\told.css"),
        ]
        adapter = GitAdapter(FAKE_REPO)
        result = adapter.get_changed_files()
        assert result == [
            FileChange(path="index.php", status="M"),
            FileChange(path="newfile.js", status="A"),
            FileChange(path="old.css", status="D"),
        ]

    @patch("hsm_sync.adapters.git_adapter.subprocess.run")
    def test_empty_diff(self, mock_run):
        mock_run.side_effect = [
            _completed("2\n"),
            _completed(""),
        ]
        adapter = GitAdapter(FAKE_REPO)
        assert adapter.get_changed_files() == []

    @patch("hsm_sync.adapters.git_adapter.subprocess.run")
    def test_initial_commit_no_diff_call(self, mock_run):
        # Only one commit — rev-list returns "1"
        mock_run.return_value = _completed("1\n")
        adapter = GitAdapter(FAKE_REPO)
        result = adapter.get_changed_files()
        assert result == []
        assert mock_run.call_count == 1  # Only rev-list called, not git diff

    @patch("hsm_sync.adapters.git_adapter.subprocess.run")
    def test_allow_empty_commit_returns_empty_diff(self, mock_run):
        mock_run.side_effect = [
            _completed("2\n"),
            _completed(""),
        ]
        adapter = GitAdapter(FAKE_REPO)
        result = adapter.get_changed_files()
        assert result == []

    @patch("hsm_sync.adapters.git_adapter.subprocess.run")
    def test_not_a_git_repo_propagates_error(self, mock_run):
        mock_run.side_effect = CalledProcessError(128, "git")
        adapter = GitAdapter(FAKE_REPO)
        with pytest.raises(CalledProcessError):
            adapter.get_changed_files()
