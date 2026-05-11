import importlib.util
import importlib
from typing import Dict

from .base_plugin import BasePlugin
import asyncio
import importlib.util
from ..core.config import settings
from loguru import logger
from importlib.abc import Loader
import os
import sys
import json
from pathlib import Path
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from ..utils.helpers import create_trigger
from apscheduler.triggers.date import DateTrigger
import re
# добавлена асинхронность
# Если load_mode установлен в parallel,оба плагина будут загружаться одновременно
# Если load_mode установлен в sequential,плагины будут загружаться по возрастанию приоритета
class PluginManager:
    plugins = {}
    plugin_configs = {}
    scheduled_tasks = {}
    _scheduler: AsyncIOScheduler = None

    @classmethod
    async def set_scheduler(cls, scheduler: AsyncIOScheduler):
        cls._scheduler = scheduler
    @classmethod
    async def load_plugin_config(cls):
        config_path = os.path.join(settings.PLUGINS_DIR, "plugins_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cls.plugin_configs = json.load(f)
                logger.info(f"Loaded plugin configuration from {config_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in plugins_config.json: {str(e)}")
            except Exception as e:
                logger.error(f"Error loading plugin configuration: {str(e)}")
        else:
            logger.warning(f"plugins_config.json not found at {config_path}")
    @classmethod
    async def load_plugin(cls, plugin_name: str,scheduler: AsyncIOScheduler = None) -> Dict[str, str]:
        if scheduler:
            await cls.set_scheduler(scheduler)
        try:
            project_root = Path(__file__).parent.parent.parent # Исправил пути сканирования плагинов
            plugins_dir = project_root / "app" / "plugins"
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            plugin_path = plugins_dir / plugin_name
            module_path = plugin_path / "__init__.py"

            if not module_path.exists():
                return {"error": f"Plugin {plugin_name} not found"}

            if plugin_name in cls.plugins:
                await cls.unload_plugin(plugin_name)
            module_name = f"app.plugins.{plugin_name}"
            spec = importlib.util.spec_from_file_location(
                module_name,
                str(module_path))
            if spec is None:
                logger.error(f"Could not create spec for {plugin_name}")
                return {"error": f"Invalid plugin module for {plugin_name}"}
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            assert isinstance(spec.loader, Loader) # костыль для  Loader(https://github.com/python/typeshed/issues/2793),
            # почему-то эксемпляр из spec.loader идет на _Loader
            spec.loader.exec_module(module)
            plugin_class_name = ''.join(
                word.capitalize() for word in plugin_name.split('_')) # Если название плагина
            # выглядит так: object_builder превращает его в Object Builder для удобства при выводе
            plugin_class = getattr(module, plugin_class_name)
            config_path = os.path.join(plugins_dir, plugin_name, "config.json")
            if not issubclass(plugin_class, BasePlugin):
                logger.error(f"Plugin {plugin_name} is not a valid plugin")
                return {"error": "Not a valid plugin"}
            cls.plugins[plugin_name] = plugin_class()

            if cls._scheduler and plugin_name in cls.plugin_configs.get("scheduled_plugins", {}):
                interval_config_link = cls.plugin_configs["scheduled_plugins"][plugin_name]
                trigger = create_trigger(interval_config_link, moscow_time=True)
                task = cls._scheduler.add_job(
                    fetch_plugin_data,
                    trigger=trigger,
                    args=[plugin_name],
                    id=f"schedule_{plugin_name}",
                    replace_existing=True
                )
                configtimevalue = interval_config_link.get("interval",
                                                           interval_config_link.get("run_at", "without interval"))

                cls.scheduled_tasks[plugin_name] = task
                logger.info(f"Scheduled {plugin_name} with interval/run_at {configtimevalue}")

            logger.info(f"Plugin {plugin_class_name} loaded successfully from {config_path}")
            return {"status": "loaded"}

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {str(e)}", exc_info=True)
            return {"error": str(e)}

    @classmethod
    def is_runnable(cls, plugin_name: str) -> bool:
        if plugin_name not in cls.plugins:
            return False
        plugin = cls.plugins[plugin_name]
        return (callable(getattr(plugin, 'start', None)) and
                callable(getattr(plugin, 'stop', None)) and
                type(plugin).start is not BasePlugin.start and
                type(plugin).stop is not BasePlugin.stop)

    @classmethod
    async def unload_plugin(cls, plugin_name: str) -> Dict[str, str]:
        if plugin_name in cls.plugins:
            await cls.plugins[plugin_name].stop()
            if plugin_name in cls.scheduled_tasks:
                cls.scheduled_tasks[plugin_name].remove()
                del cls.scheduled_tasks[plugin_name]
            del cls.plugins[plugin_name]
            if f"plugins.{plugin_name}" in sys.modules:
                del sys.modules[f"plugins.{plugin_name}"]
            logger.info(f"Plugin {plugin_name} unloaded successfully")
            return {"status": "unloaded"}
        logger.warning(f"Plugin {plugin_name} not found")
        return {"error": "Plugin not found"}

    @classmethod
    def list_plugins(cls) -> Dict[str, str]:
        return {name: plugin.get_state() for name, plugin in cls.plugins.items()}
    # Переделал под асинхроннсоть
    @classmethod
    async def get_plugin_data(cls, plugin_name: str) -> Dict[str, str]:
        if plugin_name in cls.plugins:
            return await cls.plugins[plugin_name].fetch_data()
        logger.warning(f"Plugin {plugin_name} not found")
        return {"error": "Plugin not found"}
    # закинул механизм приоритезации подгрузки плагинов в ESB
    @classmethod
    async def scan_plugins(cls, scheduler: AsyncIOScheduler):
        await cls.load_plugin_config()
        plugins_dir = settings.PLUGINS_DIR
        priorities = cls.plugin_configs.get("plugin_priorities", {})
        plugins_to_load = [p for p in os.listdir(plugins_dir) if os.path.isdir(os.path.join(plugins_dir, p)) and not p.startswith('__') and p in cls.plugin_configs.get("plugins", [])]

        sorted_plugins = sorted(plugins_to_load, key=lambda x: priorities.get(x, {}).get("priority", float('inf')))

        for plugin_name in sorted_plugins:
            if plugin_name in cls.plugin_configs.get("plugins", []):
                load_mode = priorities.get(plugin_name, {}).get("load_mode", "sequential")
                if load_mode == "parallel":
                    asyncio.create_task(cls.load_plugin(plugin_name, scheduler))
                else:
                    await cls.load_plugin(plugin_name, scheduler)
                    await asyncio.sleep(0.1)
async def fetch_plugin_data(plugin_name: str):
    if plugin_name in PluginManager.plugins:
        logger.info(f"Fetching data for {plugin_name} at {datetime.now()}")
        data = await PluginManager.get_plugin_data(plugin_name)
        if "error" in data:
            logger.error(f"Error fetching data for {plugin_name}: {data['error']}")
        else:
            logger.info(f"Successfully fetched data for {plugin_name}: {data}")
