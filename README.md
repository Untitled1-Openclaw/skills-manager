# Skills Manager

A FastAPI web app for browsing, editing, uploading, and downloading local skill files from a browser.

## Tech Stack

- Backend: FastAPI, Starlette session cookies, bcrypt password hashing
- Frontend: build-free HTML/CSS/vanilla JS SPA
- Viewer: marked for Markdown rendering, highlight.js for source highlighting
- Tests: pytest plus Playwright

## Run Locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python -m app.main
```

The app binds to `127.0.0.1:8098` by default.

Default first-run credentials:

- Username: `admin`
- Password: `admin`

Change the password from Settings after the first login. The generated config file stores a bcrypt password hash and a session secret. Set these environment variables for your own deployment:

```bash
SKILLS_MANAGER_ROOT=/home/user/.local/share/skills
SKILLS_MANAGER_CONFIG=/home/user/.config/skills-manager/config.json
SKILLS_MANAGER_DEFAULT_USER=admin
SKILLS_MANAGER_DEFAULT_PASSWORD=admin
SKILLS_MANAGER_PORT=8098
SKILLS_MANAGER_SECURE_COOKIES=true
```

## Features

- Session-based app authentication with bcrypt password hashes
- Searchable skills list with category filtering
- Skill detail tree with file metadata
- Markdown rendering with raw-source toggle
- Text file editing and save confirmation
- Binary image preview or download prompt
- Skill, category, and individual file downloads
- `.md` and `.zip` uploads into the configured `incoming/` directory
- Zip path traversal protection
- Responsive mobile and desktop UI

## Tests

```bash
pip install -r requirements.txt
python -m playwright install chromium
pytest
```

The E2E tests start a temporary server with a temporary skills root, so they do not modify your local skill files.

## Deploy

The app is intended to run as a systemd user service on localhost behind nginx at `https://example.com/skills/`.

1. Install Python dependencies in the repo environment.
2. Copy or symlink `skills-manager.service` into `~/.config/systemd/user/`.
3. Update the paths and environment variables in `skills-manager.service` for your machine.
4. Run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now skills-manager.service
```

5. Add the `/skills/` locations from `nginx.conf.example` inside the existing HTTPS `server` block for `example.com`.
6. Test and reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

The app is mounted under `/skills/`; its static and API URLs are relative so nginx can strip the `/skills/` prefix before proxying to the backend root.
Set `SKILLS_MANAGER_SECURE_COOKIES=true` for HTTPS deployments so browser session cookies are marked `Secure`.
