"""Integration contract tests for RCloneFileSystem.

These tests verify that fs.open() returns proper file-like objects
(not generators or context managers) for both read and write modes.
"""

from uuid import uuid4

import pytest


def test_open_returns_file_like_object(s3_base, rclone_fs):
    """fs.open() in read mode returns a file-like object, not a generator."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(
        Bucket=bucket_name, Key="file.txt", Body=b"test content"
    )

    f = rclone_fs.open(f"{bucket_name}/file.txt", "rb")
    try:
        assert hasattr(f, "read")
        assert hasattr(f, "seek")
        assert hasattr(f, "close")
        assert hasattr(f, "tell")
        assert not f.closed
        content = f.read()
        assert content == b"test content"
    finally:
        f.close()
    assert f.closed


def test_write_returns_file_like_object(s3_base, rclone_fs):
    """fs.open() in write mode returns a file-like object, not a generator."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    f = rclone_fs.open(f"{bucket_name}/file.txt", "wb")
    try:
        assert hasattr(f, "write")
        assert hasattr(f, "close")
        assert not f.closed
        f.write(b"written content")
    finally:
        f.close()
    assert f.closed

    # Verify the content was actually uploaded
    with rclone_fs.open(f"{bucket_name}/file.txt", "rb") as f:
        assert f.read() == b"written content"
