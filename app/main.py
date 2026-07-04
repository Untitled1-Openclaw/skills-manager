from __future__ import annotations

import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .config import change_password, ensure_config, get_settings, verify_password
from .files import (
    build_tree,
    get_skill_path,
    iter_skills,
    read_file,
    save_upload,
    safe_join,
    write_file,
    zip_category,
    zip_directory,
)


settings = get_settings()
config = ensure_config(settings)
TOKEN_TTL_SECONDS = 60 * 60 * 8
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
active_tokens: dict[str, float] = {}

app = FastAPI(title="Skills Manager")
app.add_middleware(
    SessionMiddleware,
    secret_key=config["session_secret"],
    same_site="lax",
    https_only=settings.secure_cookies,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8098", "http://localhost:8098"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginPayload(BaseModel):
    username: str
    password: str


class PasswordPayload(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class SavePayload(BaseModel):
    content: str


def _request_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return None


def _is_valid_token(token: str | None) -> bool:
    if not token:
        return False
    expires_at = active_tokens.get(token)
    if not expires_at:
        return False
    if expires_at <= time.time():
        active_tokens.pop(token, None)
        return False
    return True


def _is_valid_csrf(request: Request) -> bool:
    expected = request.session.get("csrf")
    supplied = request.headers.get("x-csrf-token")
    return bool(expected and supplied and secrets.compare_digest(str(expected), supplied))


def _is_authenticated(request: Request) -> bool:
    return bool(request.session.get("authenticated") or _is_valid_token(_request_token(request)))


def require_auth(request: Request) -> None:
    token_authenticated = _is_valid_token(_request_token(request))
    session_authenticated = bool(request.session.get("authenticated"))
    if not (session_authenticated or token_authenticated):
        raise HTTPException(status_code=401, detail="Authentication required")
    if session_authenticated and not token_authenticated and request.method.upper() not in SAFE_METHODS and not _is_valid_csrf(request):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/api/auth/me")
async def me(request: Request):
    authenticated = _is_authenticated(request)
    return {
        "authenticated": authenticated,
        "username": config["username"],
        "csrf": request.session.get("csrf") if authenticated else None,
    }


@app.post("/api/auth/login")
async def login(payload: LoginPayload, request: Request):
    if payload.username != config["username"] or not verify_password(payload.password, config["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    request.session.clear()
    request.session["authenticated"] = True
    request.session["csrf"] = secrets.token_urlsafe(24)
    token = secrets.token_urlsafe(32)
    active_tokens[token] = time.time() + TOKEN_TTL_SECONDS
    return {"ok": True, "csrf": request.session["csrf"], "token": token, "username": config["username"]}


@app.post("/api/auth/logout")
async def logout(request: Request):
    token = _request_token(request)
    if token:
        active_tokens.pop(token, None)
    request.session.clear()
    return {"ok": True}


@app.post("/api/auth/password")
async def password(payload: PasswordPayload, request: Request, _: None = Depends(require_auth)):
    global config
    if not verify_password(payload.current_password, config["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    config = change_password(settings, config, payload.new_password)
    return {"ok": True}


@app.get("/api/skills")
async def skills(_: None = Depends(require_auth)):
    return {"skills": iter_skills(settings.skills_root)}


@app.get("/api/skills/{skill_id:path}")
async def skill_detail(skill_id: str, _: None = Depends(require_auth)):
    skill = get_skill_path(settings.skills_root, skill_id)
    tree = build_tree(skill)
    return {"skill": next((item for item in iter_skills(settings.skills_root) if item["id"] == skill_id), None), "tree": tree}


@app.get("/api/files/{skill_id:path}")
async def file_read(skill_id: str, path: str, _: None = Depends(require_auth)):
    return read_file(settings.skills_root, skill_id, path)


@app.put("/api/files/{skill_id:path}")
async def file_write(skill_id: str, path: str, payload: SavePayload, _: None = Depends(require_auth)):
    return write_file(settings.skills_root, skill_id, path, payload.content)


@app.get("/api/download/skill/{skill_id:path}")
async def download_skill(skill_id: str, _: None = Depends(require_auth)):
    skill = get_skill_path(settings.skills_root, skill_id)
    if skill.is_file():
        return FileResponse(skill, filename=skill.name)
    archive = zip_directory(skill)
    return FileResponse(archive, filename=f"{skill.name}.zip", background=None)


@app.get("/api/download/category/{category}")
async def download_category(category: str, _: None = Depends(require_auth)):
    archive = zip_category(settings.skills_root, category)
    return FileResponse(archive, filename=f"{category}.zip")


@app.get("/api/download/file/{skill_id:path}")
async def download_file(skill_id: str, path: str, _: None = Depends(require_auth)):
    skill = get_skill_path(settings.skills_root, skill_id)
    base = skill.parent if skill.is_file() else skill
    file_path = safe_join(base, path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=file_path.name)


@app.post("/api/upload")
async def upload(file: UploadFile, _: None = Depends(require_auth)):
    return await save_upload(settings.skills_root, file)


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
