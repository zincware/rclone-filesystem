"""Tests for RCloneFileSystemSettings pyproject.toml loading."""

import os

import pytest


def test_settings_loads_from_pyproject_toml(tmp_path, monkeypatch):
    """Settings should read from [tool.rclone-filesystem] in pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.rclone-filesystem]\n'
        'temp_dir = "/custom/temp"\n'
        'show_progress = true\n'
        'listings_expiry_time_secs = 42.0\n'
    )
    monkeypatch.chdir(tmp_path)
    # Clear any env vars that would override
    monkeypatch.delenv("RCLONE_FS_TEMP_DIR", raising=False)
    monkeypatch.delenv("RCLONE_FS_SHOW_PROGRESS", raising=False)
    monkeypatch.delenv("RCLONE_FS_LISTINGS_EXPIRY_TIME_SECS", raising=False)

    from rclone_filesystem.settings import RCloneFileSystemSettings

    settings = RCloneFileSystemSettings()
    assert settings.temp_dir == "/custom/temp"
    assert settings.show_progress is True
    assert settings.listings_expiry_time_secs == 42.0


def test_env_vars_override_pyproject_toml(tmp_path, monkeypatch):
    """Environment variables should take precedence over pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.rclone-filesystem]\n'
        'temp_dir = "/from/toml"\n'
        'show_progress = false\n'
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RCLONE_FS_TEMP_DIR", "/from/env")
    monkeypatch.delenv("RCLONE_FS_SHOW_PROGRESS", raising=False)

    from rclone_filesystem.settings import RCloneFileSystemSettings

    settings = RCloneFileSystemSettings()
    assert settings.temp_dir == "/from/env"
    assert settings.show_progress is False


def test_defaults_when_no_pyproject_toml(tmp_path, monkeypatch):
    """Settings should use defaults when no pyproject.toml exists."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RCLONE_FS_TEMP_DIR", raising=False)
    monkeypatch.delenv("RCLONE_FS_SHOW_PROGRESS", raising=False)
    monkeypatch.delenv("RCLONE_FS_LISTINGS_EXPIRY_TIME_SECS", raising=False)

    from rclone_filesystem.settings import RCloneFileSystemSettings

    settings = RCloneFileSystemSettings()
    assert settings.temp_dir is None
    assert settings.show_progress is False
    assert settings.listings_expiry_time_secs is None
