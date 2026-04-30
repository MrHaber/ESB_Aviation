from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from prometheus_client import Counter, Histogram
from psycopg import AsyncConnection
from contextvars import ContextVar
from typing import Callable
import time
from ..database.database import get_db
from ..core.config import settings
import asyncio
from jose import JWTError, jwt
from ldap3 import Server, Connection, ALL, SUBTREE

db_context: ContextVar[AsyncConnection] = ContextVar("db_connection")

REQUEST_COUNT = Counter(
    "esb_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "esb_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint", "status"]
)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        request_id = f"req-{int(time.time())}-{id(request)}"
        response = None
        public_paths = (
            "/",
            "/openapi.json",
            "/metrics",
            "/api/v1/auth/token",
        )
        public_prefixes = (
            "/docs",
            "/redoc",
            "/static",
            "/api/v1/aviation",
        )

        logger.info(f"Request {request.method} {request.url.path} - ID: {request_id}")

        if request.url.path not in public_paths and not request.url.path.startswith(public_prefixes) and request.url.path not in [
            "/auth/login",
            "/auth/callback",
            settings.LDAP_AUTH_ROUTE,
            settings.LDAP_CALLBACK_ROUTE,
        ]:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning(f"No valid token for request {request_id}")
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized"}
                )
                return response

            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
                logger.debug(f"Validated JWT for request {request_id}: {payload.get('sub')}")
            except JWTError:
                logger.warning(f"Invalid token for request {request_id}")
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid token"}
                )
                return response

        try:
            db = db_context.get()
            if not db:
                raise RuntimeError("Database connection not found in context")

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Error processing request {request_id}: {str(e)}")
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
            raise

        finally:
            latency = time.time() - start_time
            status_code = str(response.status_code) if response else "500"

            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=status_code
            ).inc()

            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path,
                status=status_code
            ).observe(latency)

            logger.info(
                f"Response {request.method} {request.url.path} - Status: {status_code} - Latency: {latency:.2f}s - ID: {request_id}"
            )

class CORSMiddlewareConfig(CORSMiddleware):
    def __init__(self, app):
        super().__init__(
            app,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info("CORSMiddleware setup.")

async def get_db_context(request: Request, call_next: Callable):
        conn = get_db()
        token = db_context.set(conn)
        try:
            response = await call_next(request)
        finally:
            db_context.reset(token)
        return response
