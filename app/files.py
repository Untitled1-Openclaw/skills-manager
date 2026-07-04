from __future__ import annotations

import mimetypes
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile


TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".css",
    ".csv",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".log",
    ".md",
    ".py",
    ".rb",
    ".rst",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def safe_join(root: Path, *parts: str) -> Path:
    root = root.resolve()
    clean_parts: list[str] = []
    for part in parts:
        if part in {"", "."}:
            continue
        path_part = Path(part)
        if path_part.is_absolute() or ".." in path_part.parts:
            raise HTTPException(status_code=400, detail="Invalid path")
        clean_parts.extend(path_part.parts)
    target = root.joinpath(*clean_parts).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    return target


def sanitize_name(name: str) -> str:
    stem = Path(name).name.strip()
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-")
    if not sanitized:
        raise HTTPException(status_code=400, detail="Invalid file name")
    return sanitized


def parse_description(skill_md: Path) -> str:
    if not skill_md.exists() or not skill_md.is_file():
        return ""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if text.startswith("---"):
        lines = text.splitlines()
        for line in lines[1:80]:
            if line.strip() == "---":
                break
            if line.lower().startswith("description:"):
                return line.split(":", 1)[1].strip().strip("\"'")
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:180]
    return ""


def iter_skills(root: Path) -> list[dict]:
    root.mkdir(parents=True, exist_ok=True)
    incoming = root / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    skills: list[dict] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith("."):
            continue
        if entry.is_file() and entry.suffix.lower() == ".md":
            skills.append(_skill_payload(root, "root", entry.stem, entry))
            continue
        if not entry.is_dir():
            continue
        for child in sorted(entry.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith("."):
                continue
            if child.is_file() and child.suffix.lower() == ".md":
                skills.append(_skill_payload(root, entry.name, child.stem, child))
            elif child.is_dir() and (child / "SKILL.md").exists():
                skills.append(_skill_payload(root, entry.name, child.name, child))
    return skills


def _skill_payload(root: Path, category: str, name: str, path: Path) -> dict:
    skill_md = path if path.is_file() else path / "SKILL.md"
    rel = path.relative_to(root).as_posix()
    stat = path.stat()
    return {
        "id": rel,
        "name": name,
        "category": category,
        "description": parse_description(skill_md),
        "single_file": path.is_file(),
        "modified": _iso(stat.st_mtime),
    }


def get_skill_path(root: Path, skill_id: str) -> Path:
    path = safe_join(root, skill_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    if path.is_dir() and not (path / "SKILL.md").exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    if path.is_file() and path.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Skill not found")
    return path


def build_tree(path: Path) -> dict:
    if path.is_file():
        return _node(path, path.parent, include_children=False)
    return _node(path, path, include_children=True)


def _node(path: Path, base: Path, include_children: bool) -> dict:
    stat = path.stat()
    payload = {
        "name": path.name,
        "path": path.relative_to(base).as_posix(),
        "type": "directory" if path.is_dir() else "file",
        "size": stat.st_size,
        "modified": _iso(stat.st_mtime),
    }
    if include_children and path.is_dir():
        payload["children"] = [
            _node(child, base, True)
            for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            if not child.name.startswith(".")
        ]
    return payload


def read_file(root: Path, skill_id: str, file_path: str) -> dict:
    skill = get_skill_path(root, skill_id)
    base = skill.parent if skill.is_file() else skill
    path = safe_join(base, file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    rel = path.relative_to(base).as_posix()
    stat = path.stat()
    binary = not is_text_file(path)
    content = None
    if not binary:
        content = path.read_text(encoding="utf-8", errors="replace")
    return {
        "name": path.name,
        "path": rel,
        "size": stat.st_size,
        "modified": _iso(stat.st_mtime),
        "binary": binary,
        "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "content": content,
    }


def write_file(root: Path, skill_id: str, file_path: str, content: str) -> dict:
    skill = get_skill_path(root, skill_id)
    base = skill.parent if skill.is_file() else skill
    path = safe_join(base, file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if not is_text_file(path):
        raise HTTPException(status_code=400, detail="Binary files cannot be edited")
    path.write_text(content, encoding="utf-8")
    return read_file(root, skill_id, file_path)


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS or path.name in {"Dockerfile", "Makefile"}:
        return True
    try:
        sample = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\x00" not in sample


def zip_directory(source: Path) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in _iter_files(source):
            archive.write(file_path, file_path.relative_to(source.parent).as_posix())
    return Path(tmp.name)


def zip_category(root: Path, category: str) -> Path:
    source = safe_join(root, category)
    if not source.is_dir():
        raise HTTPException(status_code=404, detail="Category not found")
    return zip_directory(source)


def _iter_files(source: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if not filename.startswith("."):
                yield Path(dirpath) / filename


async def save_upload(root: Path, upload: UploadFile) -> dict:
    incoming = root / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    filename = sanitize_name(upload.filename or "")
    ext = Path(filename).suffix.lower()
    if ext not in {".md", ".zip"}:
        raise HTTPException(status_code=400, detail="Only .md and .zip uploads are supported")
    if ext == ".md":
        destination = safe_join(incoming, filename)
        with destination.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        return {"type": "markdown", "path": destination.relative_to(root).as_posix()}

    folder = incoming / sanitize_name(Path(filename).stem)
    folder.mkdir(parents=True, exist_ok=True)
    data = await upload.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                target = safe_join(folder, member.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid zip file") from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    return {"type": "zip", "path": folder.relative_to(root).as_posix()}


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
