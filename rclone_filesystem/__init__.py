from pathlib import Path

from fsspec import AbstractFileSystem
from rclone_python import rclone


class RCloneFileSystem(AbstractFileSystem):
    """Rclone filesystem"""

    def __init__(self, remote: str):
        super().__init__(remote=remote)
        self._remote = remote

    def ls(self, path, detail=False, **kwargs):
        """List files in the given path."""
        if path == "/":
            rclone_path = self._remote + ":"
        else:
            rclone_path = self._remote + ":" + path.lstrip("/")
        result = rclone.ls(rclone_path, **kwargs)
        # raise ValueError(result)
        if detail:
            return [
                {
                    "name": str(Path(path) / x["Path"]),
                    "size": x["Size"],
                    "type": "dir" if x["IsDir"] else "file",
                }
                for x in result
            ]
        return [str(Path(path) / x["Path"]) for x in result]
