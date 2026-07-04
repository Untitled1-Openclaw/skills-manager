from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def seed_skills(root: Path) -> None:
    alpha = root / "creative" / "alpha-skill"
    alpha.mkdir(parents=True)
    (alpha / "SKILL.md").write_text("---\ndescription: Alpha description\n---\n# Alpha\n\nRendered **markdown**.\n", encoding="utf-8")
    (alpha / "scripts").mkdir()
    (alpha / "scripts" / "run.py").write_text("print('alpha')\n", encoding="utf-8")
    (root / "github").mkdir()
    (root / "github" / "single.md").write_text("---\ndescription: Single file skill\n---\n# Single\n", encoding="utf-8")
    (root / "incoming").mkdir()


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    root.mkdir()
    seed_skills(root)
    return root


@pytest.fixture
def server(skills_root: Path, tmp_path: Path):
    port = free_port()
    env = os.environ.copy()
    env.update(
        {
            "SKILLS_MANAGER_ROOT": str(skills_root),
            "SKILLS_MANAGER_CONFIG": str(tmp_path / "config.json"),
            "SKILLS_MANAGER_DEFAULT_USER": "user",
            "SKILLS_MANAGER_DEFAULT_PASSWORD": "changeme123",
            "SKILLS_MANAGER_PORT": str(port),
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/api/auth/me", timeout=0.5).status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        output = process.stdout.read() if process.stdout else ""
        process.terminate()
        raise RuntimeError(f"server did not start\n{output}")
    yield base_url
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture
def login_api(server: str):
    client = httpx.Client(base_url=server)
    response = client.post("/api/auth/login", json={"username": "user", "password": "changeme123"})
    assert response.status_code == 200
    yield client
    client.close()
