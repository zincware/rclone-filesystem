# RCloneFileSystem: fsspec-Compatible Filesystem via rclone

This package provides a fsspec compliant filesystem interface for rclone.

Given an rclone remove `rclone config create myremote s3 ...` you can use the `RCloneFileSystem` as follows:

```py
from rclone_filesystem import RCloneFileSystem

fs = RCloneFileSystem(remote="myremote")

fs.ls("data") # path, e.g. bucket name for S3

with fs_a.open("data/test-file.txt", "wb") as f:
    f.write(b"Hello, World!")

with fs_b.open("data/test-file.txt", "rb") as f:
    content = f.read()
    assert content == b"Hello, World!"
```
