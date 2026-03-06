from uuid import uuid4

import pytest


@pytest.mark.parametrize("fs_key", ["s3fs_fs", "rclone_fs"])
def test_cat_file_text(s3_base, fs_key, request):
    """cat_file returns bytes content for a text file."""
    fs = request.getfixturevalue(fs_key)

    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(
        Bucket=bucket_name, Key="hello.txt", Body=b"Hello, World!"
    )

    result = fs.cat_file(f"{bucket_name}/hello.txt")
    assert result == b"Hello, World!"
    assert isinstance(result, bytes)


def test_cat_file_binary(s3_base, rclone_fs):
    """cat_file preserves binary content without corruption."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    binary_data = bytes(range(256))
    s3_base.put_object(
        Bucket=bucket_name, Key="binary.bin", Body=binary_data
    )

    result = rclone_fs.cat_file(f"{bucket_name}/binary.bin")
    assert result == binary_data
    assert isinstance(result, bytes)


def test_cat_file_not_found(s3_base, rclone_fs):
    """cat_file raises FileNotFoundError for nonexistent paths."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    with pytest.raises(FileNotFoundError):
        rclone_fs.cat_file(f"{bucket_name}/no-such-file.txt")
