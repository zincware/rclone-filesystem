from pydantic_settings import BaseSettings, SettingsConfigDict


class RCloneFileSystemSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RCLONE_FS_",
        pyproject_toml_table_header=("tool", "rclone-filesystem"),
    )
    temp_dir: str | None = None
    listings_expiry_time_secs: float | None = None
