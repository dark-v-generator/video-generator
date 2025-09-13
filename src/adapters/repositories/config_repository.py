from .interfaces import IConfigRepository, IFileRepository
from...entities.config import MainConfig
from...core.config import settings


class FileConfigRepository(IConfigRepository):
    """File-based configuration repository using IFileRepository"""

    def __init__(self, file_repository: IFileRepository):
        """Initialize with file repository dependency"""
        self._file_repository = file_repository
        self._config_collection_name = settings.config_collection_name
        self._config_id = (
            "8ebe65a7-3d10-4cfa-b1db-18edea321664"  # Just a random id to be fixed
        )

    def load_config(self) -> MainConfig:
        """Load configuration from YAML file"""
        config = self._file_repository.load_record(
            self._config_collection_name, self._config_id
        )
        if config is None:
            config = MainConfig()
            self.save_config(config)
            return config
        return MainConfig.from_bytes(config)

    def save_config(self, config: MainConfig) -> None:
        """Save configuration to YAML file"""
        self._file_repository.save_record(
            self._config_collection_name, self._config_id, config.to_bytes()
        )
