"""
We use Pydantic v2 here to facilitate settings mangement, including type hinting and secrets management.

Remember: a dotenv file and environment variables will always take priority over values loaded from the secrets directory.
"""

import logging
from os import environ
from pathlib import Path
from typing import ClassVar, Optional, Tuple, Type

from pydantic import Field, computed_field
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from url_checker.settings.custom_types import JobTypesConfig


class Settings(BaseSettings):
    """
    Most of defaults value shall apply to Dev (example: empty password).

    Prod should overide defaults.
    """

    # Super Init Constants
    # Adjust based on config location
    BASE_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent
    #
    JSON_FILE_PATH: ClassVar[Path] = Path(
        environ.get(
            "URLCHECKER_JSON_FILE_PATH", "/etc/url-checker/urlchecker_config.json"
        )
    )
    #

    envdev: bool = False
    instance_path: Path = BASE_DIR
    loglevel: str = "INFO"
    secret_key: str = "your-secret-key"
    api_token: str = "your-api-token"

    toml_config_file: Path = Path("/etc/url-checker/toml_config_file.toml")
    # Your application settings
    # ...
    ##
    rabbitmq_server: str = "172.20.0.10"
    rabbitmq_default_user: str = "guest"
    rabbitmq_default_pass: str = "guest"
    rabbitmq_vhost: str = ""

    mysql_server: str = "172.20.0.20"
    # !!! Default to None because in Prod we do not want this to be set !!!
    # Database and User should already exist and created beforehand
    # Dev facility
    mysql_root_password: Optional[str] = None
    #
    mysql_dbname: str = "urlchecker"
    mysql_user: str = "urlchecker"
    mysql_password: str = "myurlcheckerpassword"

    sqlalchemy_track_modifications: bool = False

    # Various settings
    url: dict[str, int] = {
        "max_length": 8192,
    }

    # Job type configurations with defaults
    job_types_config: JobTypesConfig = Field(default_factory=JobTypesConfig)

    # def __init__(self, _secrets_dir = "/var/run"):
    #    super()
    #    _secrets_dir = _secrets_dir

    @computed_field
    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_server}/{self.mysql_dbname}"
        )

    @computed_field
    @property
    def celery_broker_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_default_user}:{self.rabbitmq_default_pass}"
            f"@{self.rabbitmq_server}:5672/{self.rabbitmq_vhost}"
        )

    # Please note the "db" + here below, this is a celery syntax to interpret this as database backend
    @computed_field
    @property
    def celery_backend_result(self) -> str:
        return f"db+{self.sqlalchemy_database_uri}"

    model_config = SettingsConfigDict(
        env_prefix="URLCHECKER_",
        env_nested_delimiter="__",  # Allows URLCHECKER_JOB_TYPES_CONFIG__VALIDATION__TIMEOUT_SECONDS
        json_file=JSON_FILE_PATH,
        json_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields in JSON/env
        case_sensitive=False,
    )

    @computed_field
    @property
    def version(self) -> str:
        """Read version from VERSION file"""
        try:
            version_file = self.instance_path / "VERSION"
            with open(version_file, "r") as f:
                version = f.read().strip()
                # Validate format (optional)
                if not version or len(version.split(".")) < 2:
                    raise ValueError("Invalid version format")
                return version
        except (FileNotFoundError, ValueError) as e:
            logging.warning(f"Could not read VERSION file: {e}")
            return "0.0.0-dev"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """
        Customize settings sources to include JSON file.

        Priority order (highest to lowest):
        1. init_settings (arguments passed to Settings())
        2. env_settings (environment variables - highest priority for runtime)
        3. dotenv_settings (.env file)
        4. JsonConfigSettingsSource (config.json file - lowest priority)
        5. file_secret_settings (Docker secrets, etc.)
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    # Public Methods
    def print_out_config(self):
        """Log the current config behavioral settings."""
        logging.basicConfig(level=self.loglevel)
        logging.debug(f"Environment Dev Mode: {self.envdev}")
        logging.debug(f"Log Level: {self.loglevel}")
        logging.info(f"Application Version: {self.version}")


class FlaskConfig:
    def __init__(self, settings):
        # Convert Pydantic settings to Flask config format (uppercase keys)
        for key, value in settings.model_dump().items():
            setattr(self, key.upper(), value)

    def get_config(self):
        """Return configuration as dictionary"""
        return {key: value for key, value in self.__dict__.items()}


settings = Settings()
settings.print_out_config()

flask_config = FlaskConfig(settings).get_config()
