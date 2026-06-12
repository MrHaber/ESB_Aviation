from fastapi import FastAPI, HTTPException
from starlette.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse

from ..api.routes import router
from ..prometheus.logger import setup_logging
from ..prometheus.metrics import setup_metrics
from ..database.database import init_db
from ..plugins.manager import PluginManager
from ..prometheus.middleware import LoggingMiddleware, CORSMiddlewareConfig, get_db_context
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pathlib import Path
from loguru import logger
#from confluent_kafka import Producer, Consumer
from datetime import datetime
from ..utils.helpers import create_trigger
from app.core.config import settings
from ..auth.ldap import authenticate_ldap
from ..auth.auth import create_jwt_token

# Записать видос с работой системы

app = FastAPI()
# Добавить в плагин 2 конфига,
#producer_config = {
#    'bootstrap.servers': Settings.KAFKA_BOOTSTRAP_SERVERS,
#    'client.id': 'fastapi-producer'
#}
#producer = Producer(producer_config)
#consumer_config = {
#    'bootstrap.servers': 'localhost:9092',
#    'group.id': 'fastapi-group',
#    'auto.offset.reset': 'earliest'
#}
#consumer = Consumer(consumer_config)
#consumer.subscribe(['app_logs'])

templates_dir = Path(__file__).parent.parent / "templates"
setup_logging()
#app.add_middleware(MetricsMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(CORSMiddlewareConfig)
app.middleware("http")(get_db_context) # инлайн декоратор
setup_metrics(app)
app.include_router(router)
app.mount("/static", StaticFiles(directory=templates_dir), name="static")
scheduler: AsyncIOScheduler = AsyncIOScheduler()
@app.on_event("startup")
async def startup_event():
    try:
        await init_db()
    except Exception as exc:
        logger.warning(f"PostgreSQL request log database is unavailable: {exc}")

    try:
        await PluginManager.scan_plugins(scheduler)
        await setup_scheduler(scheduler)
        scheduler.start()
    except Exception as exc:
        logger.warning(f"Plugin scheduler is unavailable: {exc}")

async def setup_scheduler(scheduler):
    await PluginManager.load_plugin_config()
    scheduled_plugins = PluginManager.plugin_configs.get("scheduled_plugins", {})
    for plugin_name, config in scheduled_plugins.items():
        if plugin_name in PluginManager.plugins:
            trigger = create_trigger(config, moscow_time=True)
            task = scheduler.add_job(
                fetch_plugin_data,
                trigger=trigger,
                args=[plugin_name],
                id=f"schedule_{plugin_name}",
                replace_existing=True
            )
            PluginManager.scheduled_tasks[plugin_name] = task
            configtimevalue = config.get("interval", config.get("run_at", "without interval"))
            logger.info(f"Scheduled {plugin_name} with interval/run_at {configtimevalue}")
async def fetch_plugin_data(plugin_name: str):
    if plugin_name in PluginManager.plugins:
        logger.info(f"Fetching data for {plugin_name} at {datetime.now()}")
        data = await PluginManager.get_plugin_data(plugin_name)
        if "error" in data:
            logger.error(f"Error fetching data for {plugin_name}: {data['error']}")
        else:
            logger.info(f"Successfully fetched data for {plugin_name}: {data}")

async def periodic_plugin_check(plugin_name: str):
    await PluginManager.get_plugin_data(plugin_name)


@app.get(settings.LDAP_AUTH_ROUTE)
async def ldap_login():
    return {"message": f"Please authenticate via LDAP at {settings.LDAP_CALLBACK_ROUTE}"}


@app.post(settings.LDAP_CALLBACK_ROUTE)
async def ldap_callback(username: str, password: str):
    if not settings.LDAP_ENABLED:
        raise HTTPException(status_code=400, detail="LDAP authentication is disabled")

    user_data = await authenticate_ldap(username, password)

    jwt_payload = {
        "sub": user_data["uid"],
        "username": user_data["uid"],
        "name": user_data.get("cn", ""),
        "email": user_data.get("email", ""),
        "ldap_authenticated": True
    }

    jwt_token = create_jwt_token(jwt_payload)
    return {"user": user_data, "jwt_token": jwt_token}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        #abs path
        index_path = templates_dir / "index.html"
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        print(f"Error loading index.html: {e}")
        return HTMLResponse(content="<h1>Error loading page</h1>", status_code=500)
