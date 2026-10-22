import json
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from safer.auth import router as auth_router
from safer.bank import router as bank_router
from safer.config import Settings
from safer.documents import router as documents_router
from safer.errors import Problem
from safer.instruments import router as instruments_router
from safer.reviews import router as reviews_router
from safer.storage import client as storage_client

log = logging.getLogger("safer")
log.setLevel(logging.INFO)
if not log.handlers:
    log.addHandler(logging.StreamHandler())
log.propagate = False


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = create_engine(
        settings.database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True
    )

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="SAFER", version="0.1.0", lifespan=lifespan)
    app.state.settings, app.state.engine = settings, engine
    app.state.s3 = storage_client(settings)
    oauth = OAuth()
    oauth.register(
        "portal",
        client_id=settings.oidc_client_id,
        server_metadata_url=settings.oidc_issuer + "/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile", "code_challenge_method": "S256", "timeout": 10},
    )
    app.state.oauth = oauth
    # This signed cookie contains only the short-lived OIDC handshake, never provider tokens.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret.get_secret_value(),
        session_cookie="safer_oidc",
        max_age=600,
        same_site="lax",
        https_only=False,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        started = time.monotonic()
        response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": request.state.request_id,
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
            }
        )
        route = request.scope.get("route")
        log.info(
            json.dumps(
                {
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "route": getattr(route, "path", "unmatched"),
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )
        return response

    def problem_response(request, status, code, detail, **extra):
        return JSONResponse(
            {
                "type": "about:blank",
                "title": code.replace("_", " ").title(),
                "status": status,
                "code": code,
                "detail": detail,
                "request_id": request.state.request_id,
                **extra,
            },
            status_code=status,
            media_type="application/problem+json",
        )

    @app.exception_handler(Problem)
    async def problem_handler(request, exc):
        return problem_response(request, exc.status, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        fields = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return problem_response(
            request, 422, "validation_failed", "Check the highlighted fields.", field_errors=fields
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_handler(request, exc):
        log.error(
            json.dumps({"request_id": request.state.request_id, "error_type": type(exc).__name__})
        )
        return problem_response(
            request, 503, "storage_unavailable", "The operation could not be saved. Try again."
        )

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready"}

    app.include_router(auth_router)
    app.include_router(instruments_router)
    app.include_router(documents_router)
    app.include_router(reviews_router)
    app.include_router(bank_router)
    return app


app = create_app()
