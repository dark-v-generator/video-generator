from ..entities.config import MainConfig
from ..repositories.interfaces import IConfigRepository, IFileStorage
from ..services.interfaces import IConfigService


class ConfigService(IConfigService):
    def __init__(
        self, config_repository: IConfigRepository, file_storage: IFileStorage
    ):
        self._config_repository = config_repository
        self._file_storage = file_storage
        # Keep same file between saves
        self._watermark_custom_id = "32c3a716-bc38-4ea6-81f3-2acacc13a50d"
        self._font_custom_id = "e610c924-681b-47f8-bc49-537ed97d2e55"

    def get_config(self) -> MainConfig:
        """Get the configuration"""
        return self._config_repository.load_config()

    def save_config(self, config: MainConfig) -> None:
        """Save the configuration"""
        self._config_repository.save_config(config)

    def save_watermark(self, file_content: bytes) -> str:
        """Save the watermark file"""
        return self._file_storage.save_file(file_content, self._watermark_custom_id)

    def save_font(self, file_content: bytes) -> str:
        """Save the font file"""
        return self._file_storage.save_file(file_content, self._font_custom_id)
