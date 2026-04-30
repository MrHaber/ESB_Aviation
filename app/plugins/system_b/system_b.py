from app.plugins.base_plugin import BasePlugin
import asyncio
import websockets
from loguru import logger
import os
import json
from datetime import datetime

from app.plugins.base_plugin import PluginState

# Простой пример для работы с вебсокетом через плагин
# простейшая имплементация логики конечных автоматов
class SystemB(BasePlugin):
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        super().__init__(config_path)
        self.websocket = None
        self.state = PluginState.STOPPED

    async def fetch_data(self):
        if self.state != PluginState.RUNNING:
            return {"error": "Plugin is not running"}
        if not self.websocket or self.websocket.closed:
            return {"error": "WebSocket connection is not established"}
        try:
            await self.websocket.send("GET_DATA")
            data = await self.websocket.recv()
            return self.transform_data(data)
        except Exception as e:
            logger.error(f"Error fetching data from System B: {str(e)}")
            self.state = PluginState.ERROR
            return {"error": str(e)}

    async def start(self):
        await super().start()
        try:
            url = self.config.get("url", "ws://localhost:8765")
            self.websocket = await websockets.connect(url)
            self.state = PluginState.RUNNING
            logger.info(f"Connected to {url} for System B")
            return True
        except Exception as e:
            logger.error(f"Failed to start System B: {str(e)}")
            self.state = PluginState.ERROR
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
            return False

    async def stop(self):
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            logger.info("WebSocket connection closed for System B")
        self.state = PluginState.STOPPED
        await super().stop()
        return True
    def transform_data(self, data: str) -> dict:
        try:
            data_dict = json.loads(data)
            return {
                "source": "SystemB",
                "payload": data_dict,
                "state": self.get_state(),
                "timestamp": datetime.now().isoformat()
            }
        except json.JSONDecodeError:
            return {
                "source": "SystemB",
                "payload": {"raw": data},
                "state": self.get_state(),
                "timestamp": datetime.now().isoformat()
            }