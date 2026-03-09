from src.entities.config.image_generation import (
    ImageGenerationConfig,
    LeonardoImageGenerationConfig,
    LocalImageGenerationConfig,
)
from src.adapters.proxies.interfaces import IImageGeneratorProxy
from src.adapters.proxies.leonardo_proxy import LeonardoImageProxy
from src.adapters.proxies.local_sdxl_proxy import LocalSDXLImageProxy


class ImageGeneratorFactory:
    @staticmethod
    def create(config: ImageGenerationConfig) -> IImageGeneratorProxy:
        if isinstance(config, LeonardoImageGenerationConfig):
            return LeonardoImageProxy(config=config)
        elif isinstance(config, LocalImageGenerationConfig):
            return LocalSDXLImageProxy(config=config)
        else:
            raise ValueError(f"Unknown Image Generation Configuration: {type(config)}")
