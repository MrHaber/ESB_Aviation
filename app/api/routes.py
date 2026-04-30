from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Dict, Optional
from ..api.schemas import (
    AviationMessageSchema,
    AviationOverviewSchema,
    PluginResponse,
    RequestLogResponse,
    RoutingDecisionSchema,
    SyntheticDatasetResponse,
)
from ..auth.auth import get_current_user, create_jwt_token
from ..plugins.manager import PluginManager
from ..database.queries import get_request_logs, create_request_log
from ..database.database import get_db
from ..aviation.generator import SyntheticAviationMessageGenerator
from ..aviation.models import AviationMessage
from ..aviation.real_data import RealAviationDataImporter
from ..aviation.repository import AviationMessageRepository
from ..aviation.routing import ContextAwareAviationRouter
from ..core.config import settings
from psycopg import AsyncConnection
from datetime import datetime
import time
import asyncio
from ..auth.roles import Role
from ..utils.helpers import generate_request_id

router = APIRouter(prefix="/api/v1", tags=["API"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
aviation_repository = AviationMessageRepository(settings.AVIATION_DB_PATH)
aviation_router = ContextAwareAviationRouter()
# Добавил поддержку ролей
@router.get("/plugins", response_model=Dict[str,str])
async def list_plugins(current_user=Depends(get_current_user)):
    # Временно убрано, пытаюсь зафиксить тело с ролями
    if current_user.get("role") != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return PluginManager.list_plugins()

@router.post("/plugins/load", response_model=PluginResponse)
async def load_plugin(
    plugin_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    if current_user.get("role") != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    # темпоральные величины
    start_time = time.time()
    request_id = generate_request_id()
    result = await PluginManager.load_plugin(plugin_name)
    duration_ms = int((time.time() - start_time) * 1000)
    await create_request_log(
        db,
        request_id=request_id,
        user_id=current_user.get("sub", "anonymous"),
        plugin_name=plugin_name,
        request_payload={"action": "load"},
        response_payload=result,
        status="OK" if "status" in result else "Error",
        duration_ms=duration_ms
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.post("/plugins/unload", response_model=PluginResponse)
async def unload_plugin(
    plugin_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
):
    if current_user.get("role") != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    start_time = time.time()
    request_id = generate_request_id()
    result = await PluginManager.unload_plugin(plugin_name)
    duration_ms = int((time.time() - start_time) * 1000)
    await create_request_log(
        db,
        request_id=request_id,
        user_id=current_user.get("sub", "anonymous"),
        plugin_name=plugin_name,
        request_payload={"action": "unload"},
        response_payload=result,
        status="OK" if "status" in result else "Error",
        duration_ms=duration_ms
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/{plugin_name}/data")
async def get_plugin_data(
    plugin_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
) -> dict:
    start_time = time.time()
    request_id = generate_request_id()
    result = await PluginManager.get_plugin_data(plugin_name)
    duration_ms = int((time.time() - start_time) * 1000)
    await create_request_log(
        db,
        request_id=request_id,
        user_id=current_user.get("sub", "anonymous"),
        plugin_name=plugin_name,
        request_payload={"action": "get_data"},
        response_payload=result,
        status="OK" if "error" not in result else "Error",
        duration_ms=duration_ms
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
@router.get("/filtered-request-logs", response_model=List[RequestLogResponse])
async def get_request_logs_filtered(
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db),
    limit: Optional[int] = Query(10, ge=1),
    offset: Optional[int] = Query(0, ge=0),
    plugin_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_timestamp: Optional[datetime] = Query(None),
    end_timestamp: Optional[datetime] = Query(None)
) -> List[RequestLogResponse]:
    if current_user.get("role") != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    logs = await get_request_logs(
        db,
        limit=limit,
        offset=offset,
        plugin_name=plugin_name,
        status=status,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp
    )
    return logs
@router.post("/plugins/start", response_model=PluginResponse)
async def start_plugin(
    plugin_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
) -> Dict[str, str]:
    if current_user.get("role") != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    if plugin_name not in PluginManager.plugins:
        raise HTTPException(status_code=404, detail="Plugin not found")
    if not PluginManager.is_runnable(plugin_name):
        raise HTTPException(status_code=400, detail="Plugin is not runnable (does not override start/stop)")
    start_time: float = time.time()
    request_id: str = generate_request_id()
    result: dict = {"status": "started"} if await PluginManager.plugins[plugin_name].start() else {"error": "Failed to start"}
    duration_ms: int = int((time.time() - start_time) * 1000)
    await create_request_log(
        db,
        request_id=request_id,
        user_id=current_user.get("sub", "anonymous"),
        plugin_name=plugin_name,
        request_payload={"action": "start"},
        response_payload=result,
        status="OK" if "status" in result else "Error",
        duration_ms=duration_ms
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
@router.post("/plugins/stop", response_model=PluginResponse)
async def stop_plugin(
    plugin_name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncConnection = Depends(get_db)
) -> Dict[str, str]:
    if current_user.get("role") != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    if plugin_name not in PluginManager.plugins:
        raise HTTPException(status_code=404, detail="Plugin not found")
    if not PluginManager.is_runnable(plugin_name):
        raise HTTPException(status_code=400, detail="Plugin is not runnable (does not override start/stop)")
    start_time: float = time.time()
    request_id: str = generate_request_id()
    result: dict = {"status": "stopped"} if await PluginManager.plugins[plugin_name].stop() else {"error": "Failed to stop"}
    duration_ms: int = int((time.time() - start_time) * 1000)
    await create_request_log(
        db,
        request_id=request_id,
        user_id=current_user.get("sub", "anonymous"),
        plugin_name=plugin_name,
        request_payload={"action": "stop"},
        response_payload=result,
        status="OK" if "status" in result else "Error",
        duration_ms=duration_ms
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.get("/metrics")
async def metrics() -> None:
    #Prometheus
    pass
#TODO: Продумать лучше эту часть взято с сайта stackoverflow
@router.post("/auth/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    user_id = form_data.username
    role = Role.USER.value
    token = create_jwt_token({"sub": user_id, "role": role})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/request_logs", response_model=List[RequestLogResponse])
async def get_logs(db: AsyncConnection = Depends(get_db)) -> List[RequestLogResponse]:
    return await get_request_logs(db)


@router.post("/aviation/synthetic/generate", response_model=SyntheticDatasetResponse)
async def generate_synthetic_aviation_messages(
    count: int = Query(250, ge=1, le=10000),
    seed: int = Query(42, ge=0),
    include_real_data: bool = Query(False),
) -> SyntheticDatasetResponse:
    generator = SyntheticAviationMessageGenerator(seed=seed)
    inserted = aviation_repository.replace_messages(
        generator.generate(count=count, include_real_data=include_real_data)
    )
    return SyntheticDatasetResponse(db_path=str(aviation_repository.db_path), inserted=inserted)


@router.post("/aviation/real/import", response_model=SyntheticDatasetResponse)
async def import_real_aviation_messages() -> SyntheticDatasetResponse:
    messages = RealAviationDataImporter().fetch()
    current_messages = aviation_repository.list_messages(limit=10000)
    by_id = {message.message_id: message for message in current_messages}
    for message in messages:
        by_id[message.message_id] = message

    inserted = aviation_repository.replace_messages(by_id.values())
    return SyntheticDatasetResponse(db_path=str(aviation_repository.db_path), inserted=inserted)


@router.get("/aviation/overview", response_model=AviationOverviewSchema)
async def get_aviation_overview() -> AviationOverviewSchema:
    return AviationOverviewSchema(**aviation_repository.overview())


@router.get("/aviation/messages", response_model=List[AviationMessageSchema])
async def list_aviation_messages(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    message_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    airport: Optional[str] = Query(None),
) -> List[AviationMessageSchema]:
    messages = aviation_repository.list_messages(
        limit=limit,
        offset=offset,
        message_type=message_type,
        priority=priority,
        airport=airport,
    )
    return [AviationMessageSchema(**message.to_dict()) for message in messages]


@router.get("/aviation/messages/{message_id}", response_model=AviationMessageSchema)
async def get_aviation_message(message_id: str) -> AviationMessageSchema:
    message = aviation_repository.get_message(message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Aviation message not found")
    return AviationMessageSchema(**message.to_dict())


@router.post("/aviation/messages", response_model=AviationMessageSchema, status_code=201)
async def create_aviation_message(message: AviationMessageSchema) -> AviationMessageSchema:
    try:
        created = aviation_repository.add_message(AviationMessage.from_dict(message.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to create aviation message: {exc}")
    return AviationMessageSchema(**created.to_dict())


@router.put("/aviation/messages/{message_id}", response_model=AviationMessageSchema)
async def update_aviation_message(
    message_id: str,
    message: AviationMessageSchema,
) -> AviationMessageSchema:
    updated = aviation_repository.update_message(
        message_id,
        AviationMessage.from_dict(message.model_dump()),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Aviation message not found")
    return AviationMessageSchema(**updated.to_dict())


@router.post("/aviation/route", response_model=RoutingDecisionSchema)
async def route_aviation_message(message: AviationMessageSchema) -> RoutingDecisionSchema:
    decision = aviation_router.route(AviationMessage.from_dict(message.model_dump()))
    return RoutingDecisionSchema(**decision.to_dict())


@router.post("/aviation/messages/{message_id}/route", response_model=RoutingDecisionSchema)
async def route_stored_aviation_message(message_id: str) -> RoutingDecisionSchema:
    message = aviation_repository.get_message(message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Aviation message not found")
    decision = aviation_router.route(message)
    aviation_repository.save_routing_decision(decision)
    return RoutingDecisionSchema(**decision.to_dict())


@router.get("/aviation/routes")
async def list_aviation_routes(limit: int = Query(50, ge=1, le=500)) -> List[dict]:
    return aviation_repository.list_routing_decisions(limit=limit)
