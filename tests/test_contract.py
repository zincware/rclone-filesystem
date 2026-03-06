"""Contract verification tests for RCloneFileSystem.

These are pure unit tests that verify the fsspec contract compliance
without requiring any remote infrastructure.
"""

import pytest

from rclone_filesystem import RCloneFileSystem


def test_no_open_override():
    """RCloneFileSystem must not override open() -- only _open().

    The fsspec base class open() handles text mode wrapping, compression,
    and transaction support. Overriding it bypasses all of that.
    """
    assert "open" not in RCloneFileSystem.__dict__
    assert "_open" in RCloneFileSystem.__dict__


def test_unsupported_mode_raises():
    """Unsupported file modes raise ValueError with helpful message."""
    fs = RCloneFileSystem(remote="dummy")
    for mode in ("a", "r+", "x", "ab"):
        with pytest.raises(ValueError, match="Supported modes"):
            fs._open("some/path.txt", mode=mode)
