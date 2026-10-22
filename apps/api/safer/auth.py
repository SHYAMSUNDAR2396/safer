import httpx2 as httpx
from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from starlette.responses import RedirectResponse

from safer.errors import Problem
from safer.models import Institution, SessionRow, User
from safer.security import DB, Actor, audit, issue_session, token_hash

router = APIRouter()


@router.get("/auth/login")
async def login(request: Request):
    request.session.clear()
    try:
        return await request.app.state.oauth.portal.authorize_redirect(
            request, request.app.state.settings.app_origin + "/auth/callback", prompt="login"
        )
    except httpx.HTTPError:
        raise Problem(
            503, "identity_unavailable", "The identity service is unavailable. Try again."
        ) from None


@router.get("/auth/callback")
async def callback(request: Request, db: DB):
    try:
        token = await request.app.state.oauth.portal.authorize_access_token(request)
        claims = token.get("userinfo")
        if not claims or claims.get("iss") != request.app.state.settings.oidc_issuer:
            raise Problem(400, "invalid_login", "The identity response could not be verified.")
    except OAuthError:
        raise Problem(
            400, "invalid_login", "Login expired or could not be verified. Start again."
        ) from None
    except httpx.HTTPError:
        raise Problem(
            503, "identity_unavailable", "The identity service is unavailable. Try again."
        ) from None
    finally:
        request.session.clear()
    user = db.scalar(
        select(User).where(
            User.issuer == claims["iss"], User.subject == claims["sub"], User.active.is_(True)
        )
    )
    if not user:
        raise Problem(
            403, "not_provisioned", "An administrator must provision this account before access."
        )
    old = request.cookies.get("safer_session")
    if old:
        old_row = db.get(SessionRow, token_hash(old))
        if old_row:
            db.delete(old_row)
    opaque, _ = issue_session(db, user)
    audit(db, request, user, "session.started")
    db.commit()
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "safer_session",
        opaque,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=28800,
        path="/",
    )
    return response


@router.get("/api/v1/me")
def me(request: Request, user: Actor, db: DB):
    institution = db.get(Institution, user.institution_id)
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "role": user.role,
        "institution": {"id": str(institution.id), "name": institution.name},
        "csrf_token": request.state.csrf_token,
        "demo": True,
    }


@router.post("/auth/logout", status_code=204)
def logout(request: Request, user: Actor, db: DB):
    db.delete(db.get(SessionRow, request.state.session_hash))
    audit(db, request, user, "session.ended")
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie("safer_session", path="/")
    return response
