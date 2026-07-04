from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

from app.files import iter_skills, safe_join, save_upload


def test_cookie_authenticated_mutation_requires_csrf(login_api):
    response = login_api.put("/api/files/creative/alpha-skill", params={"path": "SKILL.md"}, json={"content": "# Bad"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid CSRF token"


def test_cookie_authenticated_mutation_accepts_csrf(login_api):
    csrf = login_api.get("/api/auth/me").json()["csrf"]
    response = login_api.put(
        "/api/files/creative/alpha-skill",
        params={"path": "SKILL.md"},
        json={"content": "# Good"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "# Good"


def test_bearer_authenticated_mutation_does_not_require_csrf(server: str):
    import httpx

    with httpx.Client(base_url=server) as client:
        login = client.post("/api/auth/login", json={"username": "user", "password": "changeme123"})
        token = login.json()["token"]
        response = client.put(
            "/api/files/creative/alpha-skill",
            params={"path": "SKILL.md"},
            json={"content": "# Bearer"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["content"] == "# Bearer"


def test_iter_skills_lists_directories_and_single_files(skills_root: Path):
    skills = iter_skills(skills_root)
    ids = {skill["id"] for skill in skills}
    assert "creative/alpha-skill" in ids
    assert "github/single.md" in ids
    alpha = next(skill for skill in skills if skill["id"] == "creative/alpha-skill")
    assert alpha["description"] == "Alpha description"


def test_safe_join_blocks_path_traversal(skills_root: Path):
    with pytest.raises(HTTPException):
        safe_join(skills_root, "../secrets")
    with pytest.raises(HTTPException):
        safe_join(skills_root, "/tmp/secrets")


@pytest.mark.asyncio
async def test_zip_upload_rejects_traversal_and_extracts_safe_files(skills_root: Path):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("ok/SKILL.md", "# OK")
        archive.writestr("../escape.txt", "bad")
    payload.seek(0)
    upload = UploadFile(filename="bundle.zip", file=payload)
    with pytest.raises(HTTPException):
        await save_upload(skills_root, upload)
    assert not (skills_root.parent / "escape.txt").exists()


@pytest.mark.asyncio
async def test_markdown_upload_goes_to_incoming(skills_root: Path):
    upload = UploadFile(filename="new-skill.md", file=io.BytesIO(b"# New"))
    result = await save_upload(skills_root, upload)
    assert result["path"] == "incoming/new-skill.md"
    assert (skills_root / "incoming" / "new-skill.md").read_text(encoding="utf-8") == "# New"
