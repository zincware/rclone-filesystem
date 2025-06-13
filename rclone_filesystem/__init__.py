import contextlib
import tempfile
from pathlib import Path

from fsspec import AbstractFileSystem
from rclone_python import rclone
from rclone_python.utils import RcloneException


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
                    "name": str(Path(path) / str(x["Path"])),
                    "size": x["Size"],
                    "type": "directory" if x["IsDir"] else "file",
                }
                for x in result
            ]
        return [str(Path(path) / str(x["Path"])) for x in result]

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
        if mode == "rb":
            # assert file exists by checking in rclone.list
            try:
                files = rclone.ls(rclone_path, **kwargs)
            except RcloneException as e:
                raise FileNotFoundError(f"File not found: {path}") from e
            if not files:
                raise FileNotFoundError(f"File not found: {path}")
            with tempfile.TemporaryDirectory() as tmp_dir:
                rclone.copy(rclone_path, tmp_dir)
                filename = next(Path(tmp_dir).glob("*"))
                with open(filename, mode) as f:
                    yield f
        elif mode == "wb":
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_file = Path(tmp_dir) / Path(path).name
                with open(tmp_file, mode) as f:
                    yield f
                rclone.copy(tmp_file.as_posix(), Path(rclone_path).parent.as_posix())
        else:
            raise ValueError(f"Unsupported mode: {mode}. Use 'rb' or 'wb'.")

    def cp_file(self, path1, path2, **kwargs):
        """Copy a file from path1 to path2."""
        if path1 == "/":
            rclone_path1 = self._remote + ":"
        else:
            rclone_path1 = self._remote + ":" + path1.lstrip("/")
        if path2 == "/":
            rclone_path2 = self._remote + ":"
        else:
            rclone_path2 = self._remote + ":" + path2.lstrip("/")
        rclone.copy(rclone_path1, rclone_path2)

    def rm_file(self, path):
        """Remove a file at the given path."""
        if path == "/":
            rclone_path = self._remote + ":"
        else:
            rclone_path = self._remote + ":" + path.lstrip("/")
        rclone.delete(rclone_path)
