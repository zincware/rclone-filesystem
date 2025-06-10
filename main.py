from rclone_filesystem import RCloneFileSystem

fs = RCloneFileSystem(remote="onedrive")

print(fs.ls("/"))
