# Skills Manager - Web App for Local Skills

## High-Level Goal

Build a polished web application that lets a user browse, view, edit, upload, and download local skill files from a browser. The skills live in a local skills directory on the same machine. The app should feel like a premium file-manager-meets-code-editor: intuitive, fast, and beautiful on both mobile and desktop.

## Context

- **Skills root:** `/home/user/.local/share/skills/`
- Skills are organized in category subdirectories (e.g. `creative/`, `github/`, `productivity/`). Some categories have a `DESCRIPTION.md`.
- Each skill is a directory containing a `SKILL.md` file plus optional supporting files in `references/`, `templates/`, `scripts/`, `assets/` subdirectories.
- Some skills are just a single `SKILL.md` file with no subdirectories.
- The app runs on the same machine as the skills (direct filesystem access).
- Deployment domain: `example.com` (nginx reverse proxy in front). The app itself binds to a localhost port; nginx terminates TLS and adds basic auth, and the app also provides app-level auth.

## Feature Requirements

### 1. Authentication
- Basic auth in front of the entire site (username + password).
- Default credentials set on first run (stored in a config file or env).
- **In-app password change:** A settings page where the user can change the password. The change takes effect immediately (no restart needed, or at most a page reload).
- Session-based or token-based — your call, but it must be secure (passwords hashed, not stored in plaintext).

### 2. Skills List (Home Page)
- Present all skills as a clean, card-based or list-based view.
- Each entry shows: skill name, category (the parent directory), and a brief description (parsed from the SKILL.md frontmatter `description:` field).
- Search/filter bar to filter skills by name or category.
- Category grouping or filtering (e.g. filter by `creative`, `github`, etc.).
- Clicking a skill opens the skill detail view.

### 3. Skill Detail View (File Tree)
- Show the skill's directory structure as a tree (folders, files including scripts, references, templates, etc.).
- For single-file skills (just a SKILL.md), show just that file.
- Clicking any file opens the file viewer/editor.
- Breadcrumb navigation back to the skills list.
- Show file metadata: size, last modified.

### 4. File Viewer / Editor
- **Viewing:** Display file contents with syntax highlighting (use a library like highlight.js, Prism, or similar). Render Markdown files as formatted HTML (with a toggle to view raw source).
- **Editing:** Allow in-browser editing of text-based files: `.md`, `.yaml`, `.yml`, `.txt`, `.json`, `.toml`, `.py`, `.sh`, `.js`, `.ts`, `.css`, `.html`, and similar text formats. Use a code editor component (CodeMirror, Monaco, or similar) with syntax highlighting.
- **Binary files** (images, etc.): Display as image preview or show "binary file, download to view."
- Save button writes changes back to the filesystem (with a confirmation dialog before overwriting).
- Show a "dirty" indicator when there are unsaved changes.

### 5. Download
- **Download entire skill as ZIP:** A button on the skill detail page that zips the whole skill directory and downloads it. If the skill is a single `.md` file, download just the `.md` file (no zip).
- **Download individual file:** A download button on each file in the viewer.
- **Download category as ZIP:** Optional but nice — download all skills in a category as a zip.

### 6. Upload
- An `/incoming` directory at `/home/user/.local/share/skills/incoming/` (create if it doesn't exist).
- Upload page/drag-drop zone where the user can upload:
  - A `.zip` file -> extract into `/incoming/<zip-name>/` (preserve folder structure).
  - A `.md` file -> save directly into `/incoming/<filename>`.
- After upload, show the uploaded skill in the incoming list with the ability to view it.
- Uploaded skills appear in the skills list under an "incoming" category.
- Show upload progress for large files.
- Validate: reject non-zip/non-md files with a clear error message.
- Prevent path traversal in zip extraction (sanitize filenames).

### 7. UX / Design Requirements
- **Outstanding UX** is the priority. This should feel like a premium product, not a utility script.
- **Fully responsive** — excellent experience on mobile (touch-friendly, no horizontal scroll, proper viewport) and desktop (keyboard shortcuts, multi-column layouts).
- Clean, modern design. Dark mode preferred (or dark mode default with light mode toggle).
- Smooth transitions and micro-interactions (file tree expand/collapse, loading states, toast notifications for actions like save/download/upload).
- Keyboard shortcuts: Ctrl+S to save in editor, Escape to close modals, etc.
- Empty states with helpful messages (no skills found, empty incoming folder, etc.).
- Error states are user-friendly, not raw stack traces.
- Loading indicators for async operations.
- Accessible: proper ARIA labels, keyboard navigation, focus management.

### 8. Technical Constraints
- **Backend:** Python (FastAPI or Flask). The app runs as a systemd user service.
- **Frontend:** Whatever you prefer — a lightweight SPA with vanilla JS + a CSS framework (Tailwind, Pico), or a small React/Vue app. The priority is a great UX, not framework choice. Keep the build simple (ideally no complex build step, or a single `npm run build`).
- **Code editor:** CodeMirror 6 or Monaco Editor for in-browser editing.
- **Syntax highlighting:** highlight.js or Prism for the file viewer.
- **ZIP handling:** Python `zipfile` or `shutil.make_archive` for download, `zipfile` for upload extraction.
- **Port:** Bind to `127.0.0.1:8098` (or another unused port — your choice, just document it).
- **Security:** Sanitize all file paths (no path traversal). Validate upload file types. Hash passwords (bcrypt or argon2).

### 9. Deployment (nginx)
- The app runs behind nginx at `example.com/skills/` (subdirectory) or a subdomain; document the chosen setup.
- Write the nginx config to `/tmp/skills-manager.nginx` and a `setup.sh` script to `/tmp/setup-skills-manager.sh` that performs all root-requiring steps (copy nginx config, nginx -t, reload). The deployment operator will run this with sudo after verifying your work.
- Create a systemd user service file for the app itself (no root needed).

### 10. Testing
- **Playwright tests** covering:
  - Login flow (correct + wrong password)
  - Password change flow
  - Skills list rendering and search
  - Skill detail view (file tree)
  - File viewing (text + markdown render)
  - File editing and saving
  - Download skill as zip
  - Upload a .md file
  - Upload a .zip file
  - Mobile viewport (responsive layout check)
- Write tests in a `tests/` directory. Include a `pytest` or `playwright` runner script.
- Also add basic unit tests for the backend API (file listing, path sanitization, zip handling).
- Run all tests before reporting completion. Fix failures.

### 11. Project Structure
```
skills-manager/
├── TASK.md              (this file)
├── README.md           (setup, run, deploy instructions)
├── app/                (backend code)
├── frontend/           (frontend assets — or static/ if no build step)
├── tests/              (playwright + unit tests)
├── skills-manager.service  (systemd user service)
├── nginx.conf.example     (nginx config template)
└── requirements.txt    (Python dependencies)
```

## Acceptance Criteria

- [ ] App starts with `python -m app.main` (or documented command) and serves on localhost
- [ ] Basic auth works — can't access any page without login
- [ ] Password change works from the UI
- [ ] Skills list shows all skills from the configured skills directory with names, categories, descriptions
- [ ] Search/filter works
- [ ] Skill detail shows file tree (or single file for simple skills)
- [ ] File viewer renders text with syntax highlighting
- [ ] Markdown files render as HTML with source toggle
- [ ] In-browser editing works for text files with save-to-disk
- [ ] Download skill as ZIP works (and plain .md for single-file skills)
- [ ] Download individual file works
- [ ] Upload .md file to /incoming works
- [ ] Upload .zip file extracts to /incoming/<name>/ works
- [ ] Path traversal is prevented in uploads
- [ ] Responsive on mobile (Playwright mobile viewport test passes)
- [ ] All Playwright tests pass
- [ ] All unit tests pass
- [ ] systemd user service file created and correct
- [ ] nginx config + setup.sh written to /tmp/
- [ ] README has clear setup and deploy instructions

## Architecture Freedom

You decide:
- Frontend framework (vanilla JS, React, Vue, Svelte; your call)
- CSS approach (Tailwind, custom CSS, component library)
- Auth implementation (JWT, session cookies, etc.)
- Whether to use a build step or keep it build-free
- Code editor library choice
- Exact API design

What's fixed:
- Python backend (FastAPI preferred, Flask acceptable)
- Must read/write to `/home/user/.local/share/skills/`
- Must bind to localhost (nginx in front)
- Playwright for E2E tests

## Self-Summary

At the very end of your work, print a public-safe summary containing: architecture overview, tech stack chosen, files created, how to run locally, how to deploy, test results (pass/fail counts), port number, default credentials, and any known limitations or remaining issues. Print this as your final message so it can be relayed directly.

Before finishing, run all tests. If they fail, analyze the output and fix the issues. Only report "Done" when all tests pass.
