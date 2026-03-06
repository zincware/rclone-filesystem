"""Tests for show_progress and pbar parameter forwarding."""

from unittest.mock import MagicMock, patch

import pytest

from rclone_filesystem import RCloneFile, RCloneFileSystem
from rclone_filesystem.settings import RCloneFileSystemSettings


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


def test_show_progress_setting_default_false():
    settings = RCloneFileSystemSettings()
    assert settings.show_progress is False


def test_show_progress_setting_env_var(monkeypatch):
    monkeypatch.setenv("RCLONE_FS_SHOW_PROGRESS", "true")
    settings = RCloneFileSystemSettings()
    assert settings.show_progress is True


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


@patch("rclone_filesystem.rclone.ls", return_value=[])
def test_show_progress_default_false(mock_ls):
    fs = RCloneFileSystem(remote="test", skip_instance_cache=True)
    assert fs._show_progress is False


@patch("rclone_filesystem.rclone.ls", return_value=[])
def test_show_progress_constructor_true(mock_ls):
    fs = RCloneFileSystem(remote="test", show_progress=True, skip_instance_cache=True)
    assert fs._show_progress is True


@patch("rclone_filesystem.rclone.ls", return_value=[])
def test_show_progress_env_var(mock_ls, monkeypatch):
    monkeypatch.setenv("RCLONE_FS_SHOW_PROGRESS", "true")
    fs = RCloneFileSystem(remote="test", skip_instance_cache=True)
    assert fs._show_progress is True


@patch("rclone_filesystem.rclone.ls", return_value=[])
def test_show_progress_constructor_overrides_env(mock_ls, monkeypatch):
    monkeypatch.setenv("RCLONE_FS_SHOW_PROGRESS", "true")
    fs = RCloneFileSystem(remote="test", show_progress=False, skip_instance_cache=True)
    assert fs._show_progress is False


# ---------------------------------------------------------------------------
# put_file forwarding tests
# ---------------------------------------------------------------------------


@patch("os.path.exists", return_value=True)
@patch("rclone_filesystem.rclone.copyto")
@patch("rclone_filesystem.rclone.ls", return_value=[])
def test_put_file_forwards_show_progress(mock_ls, mock_copyto, mock_exists):
    fs = RCloneFileSystem(remote="test", skip_instance_cache=True)
    fs.put_file("/tmp/local.txt", "remote.txt", show_progress=True)
    mock_copyto.assert_called_once()
    assert mock_copyto.call_args.kwargs["show_progress"] is True


@patch("os.path.exists", return_value=True)
@patch("rclone_filesystem.rclone.copyto")
@patch("rclone_filesystem.rclone.ls", return_value=[])
def test_put_file_forwards_pbar(mock_ls, mock_copyto, mock_exists):
    fs = RCloneFileSystem(remote="test", skip_instance_cache=True)
    mock_pbar = MagicMock()
    fs.put_file("/tmp/local.txt", "remote.txt", pbar=mock_pbar)
    mock_copyto.assert_called_once()
    assert mock_copyto.call_args.kwargs["pbar"] is mock_pbar


@patch("os.path.exists", return_value=True)
@patch("rclone_filesystem.rclone.copyto")
@patch("rclone_filesystem.rclone.ls", return_value=[])
def test_put_file_per_call_overrides_instance(mock_ls, mock_copyto, mock_exists):
    fs = RCloneFileSystem(remote="test", show_progress=True, skip_instance_cache=True)
    fs.put_file("/tmp/local.txt", "remote.txt", show_progress=False)
    mock_copyto.assert_called_once()
    assert mock_copyto.call_args.kwargs["show_progress"] is False


# ---------------------------------------------------------------------------
# get_file forwarding tests
# ---------------------------------------------------------------------------


@patch("os.path.exists", return_value=True)
@patch("rclone_filesystem.rclone.copyto")
@patch("rclone_filesystem.rclone.ls", return_value=[])
def test_get_file_forwards_show_progress(mock_ls, mock_copyto, mock_exists):
    fs = RCloneFileSystem(remote="test", skip_instance_cache=True)
    fs.get_file("remote.txt", "/tmp/local.txt", show_progress=True)
    mock_copyto.assert_called_once()
    assert mock_copyto.call_args.kwargs["show_progress"] is True


# ---------------------------------------------------------------------------
# cp_file forwarding tests
# ---------------------------------------------------------------------------


@patch("rclone_filesystem.rclone.copyto")
@patch("rclone_filesystem.rclone.ls", return_value=[{"Path": "src.txt", "Size": 10, "IsDir": False}])
def test_cp_file_forwards_show_progress(mock_ls, mock_copyto):
    fs = RCloneFileSystem(remote="test", skip_instance_cache=True)
    fs.cp_file("src.txt", "dst.txt", show_progress=True)
    mock_copyto.assert_called_once()
    assert mock_copyto.call_args.kwargs["show_progress"] is True


# ---------------------------------------------------------------------------
# RCloneFile tests
# ---------------------------------------------------------------------------


@patch("rclone_filesystem.rclone.copy")
def test_rclonefile_inherits_show_progress(mock_copy):
    """RCloneFile read mode passes fs._show_progress to rclone.copy."""
    fs = MagicMock()
    fs._show_progress = True
    fs._temp_dir = None
    fs._make_rclone_path.return_value = "test:file.txt"

    # Mock tempfile so RCloneFile.__init__ can work
    with patch("rclone_filesystem.tempfile.mkdtemp", return_value="/tmp/fake"), \
         patch("rclone_filesystem.Path") as mock_path:
        mock_path.return_value.iterdir.return_value = ["/tmp/fake/file.txt"]
        with patch("builtins.open", MagicMock()):
            f = RCloneFile(fs, "file.txt", "rb")
    mock_copy.assert_called_once()
    assert mock_copy.call_args.kwargs["show_progress"] is True


@patch("rclone_filesystem.rclone.copyto")
def test_rclonefile_close_forwards_show_progress(mock_copyto):
    """RCloneFile write mode close passes show_progress to rclone.copyto."""
    fs = MagicMock()
    fs._show_progress = True
    fs._temp_dir = None
    fs._make_rclone_path.return_value = "test:file.txt"

    with patch("rclone_filesystem.tempfile.mkdtemp", return_value="/tmp/fake"), \
         patch("rclone_filesystem.Path") as mock_path:
        mock_path.return_value.__truediv__ = MagicMock(return_value=MagicMock(as_posix=MagicMock(return_value="/tmp/fake/file.txt")))
        mock_path.return_value.__truediv__.return_value.name = "file.txt"
        with patch("builtins.open", MagicMock()):
            f = RCloneFile(fs, "file.txt", "wb")
    f.close()
    mock_copyto.assert_called_once()
    assert mock_copyto.call_args.kwargs["show_progress"] is True
