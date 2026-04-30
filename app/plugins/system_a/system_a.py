from app.plugins.base_plugin import BasePlugin
import aiohttp
from app.transformers.xml_to_json import xml_to_json
from app.transformers.odata_to_json import odata_to_json
from app.transformers.csv_to_json import csv_to_json
from app.transformers.binary_to_json import binary_to_json
from app.plugins.base_plugin import PluginState
from loguru import logger
import os
# Пример плагина с трансформацией данных с некоторого сервисаи
class SystemA(BasePlugin):
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        super().__init__(config_path)
    async def fetch_data(self):
        url = self.config.get("url")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    raw_data = await response.text()
                    return await self._transform_data(raw_data)
        except Exception as e:
            logger.error(f"Error fetching data from System A: {str(e)}")
            return {"error": str(e)}
    async def _transform_data(self, raw_data: str):
        for parser, name in [
            (xml_to_json, "xml"),
            (odata_to_json, "odata"),
            (csv_to_json, "csv"),
            (lambda d: binary_to_json(d.encode()), "binary"),
        ]:
            try:
                parsed = parser(raw_data)
                return self.transform_data(parsed)
            except Exception:
                continue

        raise ValueError("Unknown data format")