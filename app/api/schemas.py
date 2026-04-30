from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, List, Optional

class PluginResponse(BaseModel):
    status: Optional[str] = None
    error: Optional[str] = None

class RequestLogResponse(BaseModel):
    id: str
    timestamp: datetime
    user_id: str
    plugin_name: str
    request_payload: Dict[str, Any]
    response_payload: Dict[str, Any]
    status: str
    duration_ms: int


class AviationMessageSchema(BaseModel):
    message_id: str
    message_type: str
    priority: str = "NORMAL"
    origin_airport: str
    destination_airport: str
    flight_number: str
    operator: str
    received_at: datetime
    payload: Dict[str, Any]
    aircraft_registration: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class RoutingDecisionSchema(BaseModel):
    message_id: str
    route_key: str
    destinations: List[str]
    priority_channel: str
    reasons: List[str]
    ttl_seconds: int


class SyntheticDatasetResponse(BaseModel):
    db_path: str
    inserted: int


class AviationOverviewSchema(BaseModel):
    total_messages: int
    routed_messages: int
    message_types: Dict[str, int]
    priorities: Dict[str, int]
    source_systems: Dict[str, int]
