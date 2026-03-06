from uuid import uuid4

import pytest


def test_ls_caches_results(s3_base, rclone_fs):
    """ls() populates DirCache; second call returns cached result."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="a.txt", Body=b"aaa")

    # First call populates cache
    result1 = rclone_fs.ls(bucket_name)
    assert bucket_name in rclone_fs.dircache

    # Second call returns same data (from cache)
    result2 = rclone_fs.ls(bucket_name)
    assert result1 == result2


def test_ls_refresh_bypasses_cache(s3_base, rclone_fs):
    """ls(refresh=True) fetches fresh data, picking up new files."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="a.txt", Body=b"aaa")

    result1 = rclone_fs.ls(bucket_name)
    assert len(result1) == 1

    # Add a file behind the cache's back
    s3_base.put_object(Bucket=bucket_name, Key="b.txt", Body=b"bbb")

    # Without refresh, cache still returns old result
    result_cached = rclone_fs.ls(bucket_name)
    assert len(result_cached) == 1

    # With refresh, new file appears
    result_refreshed = rclone_fs.ls(bucket_name, refresh=True)
    assert len(result_refreshed) == 2
    assert f"{bucket_name}/b.txt" in result_refreshed


def test_invalidate_cache_specific_path(s3_base, rclone_fs):
    """invalidate_cache(path) removes that path from DirCache."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="a.txt", Body=b"aaa")

    rclone_fs.ls(bucket_name)
    assert bucket_name in rclone_fs.dircache

    rclone_fs.invalidate_cache(bucket_name)
    assert bucket_name not in rclone_fs.dircache


def test_invalidate_cache_all(s3_base, rclone_fs):
    """invalidate_cache() with no args clears the entire DirCache."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="a.txt", Body=b"aaa")

    rclone_fs.ls(bucket_name)
    assert len(rclone_fs.dircache) > 0

    rclone_fs.invalidate_cache()
    assert len(rclone_fs.dircache) == 0


def test_put_invalidates_cache(s3_base, rclone_fs, tmp_path):
    """After put_file, dircache for parent path is cleared."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="existing.txt", Body=b"data")

    # Populate cache
    rclone_fs.ls(bucket_name)
    assert bucket_name in rclone_fs.dircache

    # Put a new file
    local_file = tmp_path / "newfile.txt"
    with local_file.open("wb") as f:
        f.write(b"new content")
    rclone_fs.put(local_file.as_posix(), f"{bucket_name}/newfile.txt")

    # Cache should be invalidated
    assert bucket_name not in rclone_fs.dircache

    # Fresh ls should show new file
    result = rclone_fs.ls(bucket_name)
    assert f"{bucket_name}/newfile.txt" in result


def test_rm_file_invalidates_cache(s3_base, rclone_fs):
    """After rm_file, dircache for parent path is cleared."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="file.txt", Body=b"data")

    # Populate cache
    rclone_fs.ls(bucket_name)
    assert bucket_name in rclone_fs.dircache

    # Remove file
    rclone_fs.rm_file(f"{bucket_name}/file.txt")

    # Cache should be invalidated
    assert bucket_name not in rclone_fs.dircache

    # Fresh ls should not show deleted file
    result = rclone_fs.ls(bucket_name)
    assert f"{bucket_name}/file.txt" not in result


def test_cp_file_invalidates_cache(s3_base, rclone_fs):
    """After cp_file, dircache for destination parent is cleared."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)
    s3_base.put_object(Bucket=bucket_name, Key="file.txt", Body=b"data")

    # Populate cache
    rclone_fs.ls(bucket_name)
    assert bucket_name in rclone_fs.dircache

    # Copy file
    rclone_fs.cp_file(f"{bucket_name}/file.txt", f"{bucket_name}/copy.txt")

    # Cache should be invalidated
    assert bucket_name not in rclone_fs.dircache

    # Fresh ls should show both files
    result = rclone_fs.ls(bucket_name)
    assert f"{bucket_name}/file.txt" in result
    assert f"{bucket_name}/copy.txt" in result


def test_write_close_invalidates_cache(s3_base, rclone_fs):
    """After fs.open('wb') + write + close, dircache is cleared."""
    bucket_name = uuid4().hex
    s3_base.create_bucket(Bucket=bucket_name)

    # Populate cache with empty bucket listing
    rclone_fs.ls(bucket_name)
    assert bucket_name in rclone_fs.dircache

    # Write via open
    with rclone_fs.open(f"{bucket_name}/written.txt", "wb") as f:
        f.write(b"written data")

    # Cache should be invalidated after close
    assert bucket_name not in rclone_fs.dircache

    # Fresh ls should show new file
    result = rclone_fs.ls(bucket_name)
    assert f"{bucket_name}/written.txt" in result
