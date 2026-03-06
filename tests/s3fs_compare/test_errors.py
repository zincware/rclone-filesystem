from uuid import uuid4

import pytest


def test_put_file_missing_local(s3_base, rclone_fs, tmp_path):
    """put_file with nonexistent local path should raise FileNotFoundError."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    nonexistent = tmp_path / "no-such-file.txt"
    remote_path = f"{bucket_name}/dest.txt"

    with pytest.raises(FileNotFoundError):
        rclone_fs.put_file(nonexistent.as_posix(), remote_path)


def test_get_file_missing_remote(s3_base, rclone_fs, tmp_path):
    """get_file with nonexistent remote path should raise FileNotFoundError."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    local_path = tmp_path / "output.txt"
    remote_path = f"{bucket_name}/no-such-file.txt"

    with pytest.raises(FileNotFoundError):
        rclone_fs.get_file(remote_path, local_path.as_posix())


def test_cp_file_missing_source(s3_base, rclone_fs):
    """cp_file with nonexistent source should raise FileNotFoundError."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    with pytest.raises(FileNotFoundError):
        rclone_fs.cp_file(
            f"{bucket_name}/no-such-file.txt",
            f"{bucket_name}/dest.txt",
        )
