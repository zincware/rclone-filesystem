from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key_a", ["s3fs_fs", "rclone_fs"])
@pytest.mark.parametrize("fs_key_b", ["s3fs_fs", "rclone_fs"])
def test_write_file(s3_base, fs_key_a, fs_key_b, request):
    fs_a = request.getfixturevalue(fs_key_a)
    fs_b = request.getfixturevalue(fs_key_b)

    bucket_name = uuid4().hex

    s3_base.create_bucket(Bucket=bucket_name)

    with fs_a.open(f"{bucket_name}/test-file.txt", "wb") as f:
        f.write(b"Hello, World!")

    # Verify the file was written correctly
    with fs_b.open(f"{bucket_name}/test-file.txt", "rb") as f:
        content = f.read()
        assert content == b"Hello, World!"


@pytest.mark.parametrize("fs_key_a", ["s3fs_fs", "rclone_fs"])
@pytest.mark.parametrize("fs_key_b", ["s3fs_fs", "rclone_fs"])
def test_write_nested_path(s3_base, fs_key_a, fs_key_b, request):
    fs_a = request.getfixturevalue(fs_key_a)
    fs_b = request.getfixturevalue(fs_key_b)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    with fs_a.open(f"{bucket_name}/deep/nested/dir/file.txt", "wb") as f:
        f.write(b"nested content")

    with fs_b.open(f"{bucket_name}/deep/nested/dir/file.txt", "rb") as f:
        content = f.read()
        assert content == b"nested content"


@pytest.mark.parametrize("fs_key_a", ["s3fs_fs", "rclone_fs"])
@pytest.mark.parametrize("fs_key_b", ["s3fs_fs", "rclone_fs"])
def test_write_overwrite_existing(s3_base, fs_key_a, fs_key_b, request):
    fs_a = request.getfixturevalue(fs_key_a)
    fs_b = request.getfixturevalue(fs_key_b)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(
        Bucket=bucket_name, Key="overwrite.txt", Body=b"original content"
    )

    with fs_a.open(f"{bucket_name}/overwrite.txt", "wb") as f:
        f.write(b"new content")

    with fs_b.open(f"{bucket_name}/overwrite.txt", "rb") as f:
        content = f.read()
        assert content == b"new content"


@pytest.mark.parametrize("fs_key_a", ["s3fs_fs", "rclone_fs"])
@pytest.mark.parametrize("fs_key_b", ["s3fs_fs", "rclone_fs"])
def test_write_empty_file(s3_base, fs_key_a, fs_key_b, request):
    fs_a = request.getfixturevalue(fs_key_a)
    fs_b = request.getfixturevalue(fs_key_b)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    with fs_a.open(f"{bucket_name}/empty.txt", "wb") as f:
        pass  # write nothing, just open and close

    with fs_b.open(f"{bucket_name}/empty.txt", "rb") as f:
        content = f.read()
        assert content == b""


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_write_then_read_roundtrip(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    with fs.open(f"{bucket_name}/roundtrip.txt", "wb") as f:
        f.write(b"roundtrip data")

    with fs.open(f"{bucket_name}/roundtrip.txt", "rb") as f:
        content = f.read()
        assert content == b"roundtrip data"


@pytest.mark.parametrize("fs_key_a", ["s3fs_fs", "rclone_fs"])
@pytest.mark.parametrize("fs_key_b", ["s3fs_fs", "rclone_fs"])
def test_write_special_characters_in_filename(s3_base, fs_key_a, fs_key_b, request):
    fs_a = request.getfixturevalue(fs_key_a)
    fs_b = request.getfixturevalue(fs_key_b)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    with fs_a.open(f"{bucket_name}/file with spaces.txt", "wb") as f:
        f.write(b"special chars content")

    with fs_b.open(f"{bucket_name}/file with spaces.txt", "rb") as f:
        content = f.read()
        assert content == b"special chars content"
