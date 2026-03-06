from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.main import PyprojectTomlConfigSettingsSource


class RCloneFileSystemSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RCLONE_FS_",
        pyproject_toml_table_header=("tool", "rclone-filesystem"),
    )
    temp_dir: str | None = None
    listings_expiry_time_secs: float | None = None
    show_progress: bool = False

    @classmethod
    def settings_customise_sources(cls, settings_cls, **kwargs):
        return (
            kwargs["init_settings"],
            kwargs["env_settings"],
            kwargs["dotenv_settings"],
            PyprojectTomlConfigSettingsSource(settings_cls),
            kwargs["file_secret_settings"],
        )
