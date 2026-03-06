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
