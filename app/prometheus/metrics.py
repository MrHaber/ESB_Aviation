from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI
from prometheus_client import Gauge
from app.plugins.manager import PluginManager
import asyncio
# количество операций,
# количество запросов к ручкам
# посмотреть в разрезе
PLUGIN_STATE_GAUGE = Gauge(
    "plugin_state",
    "State of each plugin (0 = stopped, 1 = running, 2 = error)",
    ["plugin_name"]
)

def setup_metrics(app: FastAPI):
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        excluded_handlers=["/metrics"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    instrumentator.instrument(app).expose(app, include_in_schema=False)

    @app.on_event("startup")
    async def start_plugin_metrics_updater():
        async def update_plugin_metrics():
            while True:
                for plugin_name, plugin in PluginManager.plugins.items():
                    try:
                        state_str = plugin.get_state()
                        state_value = {"stopped": 0, "running": 1, "error": 2}.get(state_str, 2)
                        PLUGIN_STATE_GAUGE.labels(plugin_name=plugin_name).set(state_value)
                    except Exception as e:
                        PLUGIN_STATE_GAUGE.labels(plugin_name=plugin_name).set(2)
                await asyncio.sleep(10)

        asyncio.create_task(update_plugin_metrics())