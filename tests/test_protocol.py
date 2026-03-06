"""Tests for fsspec protocol registration, _strip_protocol, and _get_kwargs_from_urls."""

import pytest

from rclone_filesystem import RCloneFileSystem


class TestProtocolAttributes:
    def test_protocol_is_rclone(self):
        assert RCloneFileSystem.protocol == "rclone"

    def test_root_marker_is_empty(self):
        assert RCloneFileSystem.root_marker == ""


class TestStripProtocol:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("rclone://myremote/bucket/key", "bucket/key"),
            ("rclone://myremote:bucket/key", "bucket/key"),
            ("rclone://myremote", ""),
            ("rclone://myremote/", ""),
            ("rclone://myremote:", ""),
            ("bucket/key", "bucket/key"),
            ("", ""),
        ],
        ids=[
            "slash-separator",
            "colon-separator",
            "remote-only",
            "remote-trailing-slash",
            "remote-trailing-colon",
            "passthrough-no-protocol",
            "empty-string",
        ],
    )
    def test_strip_protocol(self, url, expected):
        assert RCloneFileSystem._strip_protocol(url) == expected

    def test_strip_protocol_list_input(self):
        result = RCloneFileSystem._strip_protocol(
            ["rclone://r/a", "rclone://r/b"]
        )
        assert result == ["a", "b"]


class TestGetKwargsFromUrls:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("rclone://myremote/path", {"remote": "myremote"}),
            ("rclone://myremote:path", {"remote": "myremote"}),
            ("rclone://myremote", {"remote": "myremote"}),
            ("bucket/key", {}),
        ],
        ids=[
            "slash-separator",
            "colon-separator",
            "remote-only",
            "no-protocol",
        ],
    )
    def test_get_kwargs_from_urls(self, url, expected):
        assert RCloneFileSystem._get_kwargs_from_urls(url) == expected


class TestFsspecDiscovery:
    def test_filesystem_discovery(self):
        import fsspec

        fs = fsspec.filesystem("rclone", remote="s3-test")
        assert isinstance(fs, RCloneFileSystem)
        assert fs._remote == "s3-test"
