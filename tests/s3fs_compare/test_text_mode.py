from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_text_read(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(
        Bucket=bucket_name, Key="file.txt", Body=b"Hello, text mode!"
    )

    with fs.open(f"{bucket_name}/file.txt", "r") as f:
        content = f.read()
        assert content == "Hello, text mode!"
        assert isinstance(content, str)


@pytest.mark.parametrize("fs_key_a", ["s3fs_fs", "rclone_fs"])
@pytest.mark.parametrize("fs_key_b", ["s3fs_fs", "rclone_fs"])
def test_text_write(s3_base, fs_key_a, fs_key_b, request):
    fs_a = request.getfixturevalue(fs_key_a)
    fs_b = request.getfixturevalue(fs_key_b)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    with fs_a.open(f"{bucket_name}/file.txt", "w") as f:
        f.write("Hello from text mode!")

    with fs_b.open(f"{bucket_name}/file.txt", "rb") as f:
        content = f.read()
        assert content == b"Hello from text mode!"


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_text_roundtrip(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    original = "Text roundtrip content with special chars: @#$%"

    with fs.open(f"{bucket_name}/roundtrip.txt", "w") as f:
        f.write(original)

    with fs.open(f"{bucket_name}/roundtrip.txt", "r") as f:
        content = f.read()
        assert content == original


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_text_read_utf8(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(
        Bucket=bucket_name,
        Key="utf8.txt",
        Body="Hallo Welt! Gruesse!".encode("utf-8"),
    )

    with fs.open(f"{bucket_name}/utf8.txt", "r") as f:
        content = f.read()
        assert content == "Hallo Welt! Gruesse!"


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_text_newline_handling(s3_base, fs_key, request):
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(
        Bucket=bucket_name,
        Key="newlines.txt",
        Body=b"line1\r\nline2\rline3\nline4",
    )

    with fs.open(f"{bucket_name}/newlines.txt", "r") as f:
        content = f.read()
        # Universal newline mode normalizes \r\n and \r to \n
        assert content == "line1\nline2\nline3\nline4"
