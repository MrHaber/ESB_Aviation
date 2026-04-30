from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime
import json
import os
from loguru import logger
# Абстрактный класс для плагинов
# Адаптирован под ТЗ, думаю надо будет предусмотреть возможность отслеживания выгрузки
# в обработчике
# Добавлено 'состояние' плагина
class PluginState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"
class BasePlugin(ABC):
    def __init__(self, config_path: str = None):
        self.state = PluginState.STOPPED
        self.config = {}
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded config for {self.__class__.__name__} from {config_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in config for {self.__class__.__name__}: {str(e)}")
                self.state = PluginState.ERROR
            except Exception as e:
                logger.error(f"Error loading config for {self.__class__.__name__}: {str(e)}")
                self.state = PluginState.ERROR

    @abstractmethod
    async def fetch_data(self):
        pass

    async def start(self):
        self.state = PluginState.RUNNING
        logger.info(f"Started plugin {self.__class__.__name__}")

    async def stop(self):
        self.state = PluginState.STOPPED
        logger.info(f"Stopped plugin {self.__class__.__name__}")

    def get_state(self):
        return self.state.value

    def transform_data(self, data):
        return {
            "source": self.__class__.__name__,
            "timestamp": datetime.now().isoformat(),
            "payload": data,
            "state": self.get_state()
        }