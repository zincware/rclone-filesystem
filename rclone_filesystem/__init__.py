import contextlib
import tempfile
from pathlib import Path

from fsspec import AbstractFileSystem
from rclone_python import rclone


class RCloneFileSystem(AbstractFileSystem):
    """Rclone filesystem"""

    def __init__(self, remote: str):
        super().__init__(remote=remote)
        self._remote = remote

    def ls(self, path, detail=False, **kwargs):
        """List files in the given path.

        Limitations
        -----------
        - This will not raise ``FileNotFoundError`` if the path
            does not exist, but will return an empty list.
        """
        if path == "/":
            rclone_path = self._remote + ":"
        else:
            rclone_path = self._remote + ":" + path.lstrip("/")
        result = rclone.ls(rclone_path, **kwargs)

        if detail:
            return [
                {
                    "name": str(Path(path) / x["Path"]),
                    "size": x["Size"],
                    "type": "directory" if x["IsDir"] else "file",
                }
                for x in result
            ]
        return [str(Path(path) / x["Path"]) for x in result]

    @contextlib.contextmanager
    def open(
        self,
        path,
        mode="rb",
        block_size=None,
        cache_options=None,
        compression=None,
        **kwargs,
    ):
        if path == "/":
            rclone_path = self._remote + ":"
        else:
            rclone_path = self._remote + ":" + path.lstrip("/")
        with tempfile.TemporaryDirectory() as tmp_dir:
            rclone.copy(rclone_path, tmp_dir)
            filename = next(Path(tmp_dir).glob("*"))
            with open(filename, mode) as f:
                yield f
