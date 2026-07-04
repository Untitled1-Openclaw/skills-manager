const state = {
  token: localStorage.getItem("skills-manager-token"),
  csrf: null,
  skills: [],
  categories: [],
  selectedFile: null,
  editorDirty: false,
  currentSkill: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const view = $("#view");
const basePath = new URL(".", window.location.href).pathname;

function appUrl(path) {
  return `${basePath}${path.replace(/^\/+/, "")}`;
}

async function api(path, options = {}) {
  const headers = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (state.csrf && !["GET", "HEAD", "OPTIONS"].includes((options.method || "GET").toUpperCase())) {
    headers["X-CSRF-Token"] = state.csrf;
  }
  const response = await fetch(appUrl(path), { credentials: "same-origin", ...options, headers: { ...headers, ...(options.headers || {}) } });
  if (!response.ok) {
    let message = "Request failed";
    try {
      message = (await response.json()).detail || message;
    } catch (_) {}
    throw new Error(message);
  }
  return response.json();
}

function toast(message) {
  const item = document.createElement("div");
  item.className = "toast";
  item.textContent = message;
  $("#toast").append(item);
  setTimeout(() => item.remove(), 3200);
}

function setTitle(eyebrow, title) {
  $("#section-eyebrow").textContent = eyebrow;
  $("#section-title").textContent = title;
}

function showLogin() {
  $("#login-screen").hidden = false;
  $("#app-shell").hidden = true;
  $("#app-shell").inert = true;
  $("#login-screen").inert = false;
  document.body.classList.add("auth-visible");
}

function showApp() {
  $("#login-screen").hidden = true;
  $("#app-shell").hidden = false;
  $("#login-screen").inert = true;
  $("#app-shell").inert = false;
  document.body.classList.remove("auth-visible");
}

function route() {
  $(".sidebar").classList.remove("open");
  const hash = location.hash || "#/";
  document.querySelectorAll("[data-nav]").forEach((link) => link.classList.toggle("active", link.getAttribute("href") === hash));
  if (hash.startsWith("#/skill/")) return renderSkill(decodeURIComponent(hash.slice(8)));
  if (hash === "#/upload") return renderUpload();
  if (hash === "#/settings") return renderSettings();
  return renderHome();
}

async function boot() {
  state.token = localStorage.getItem("skills-manager-token");
  const me = await api("/api/auth/me");
  if (!me.authenticated) {
    state.csrf = null;
    showLogin();
    return;
  }
  state.csrf = me.csrf || state.csrf;
  showApp();
  route();
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#login-error").textContent = "";
  try {
    const payload = Object.fromEntries(new FormData(event.currentTarget));
    const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify(payload) });
    state.token = data.token;
    state.csrf = data.csrf;
    localStorage.setItem("skills-manager-token", data.token);
    await boot();
  } catch (error) {
    $("#login-error").textContent = error.message;
  }
});

$("#logout-button").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" });
  localStorage.removeItem("skills-manager-token");
  state.token = null;
  state.csrf = null;
  location.hash = "#/";
  await boot();
});

$("#mobile-menu").addEventListener("click", () => $(".sidebar").classList.toggle("open"));
window.addEventListener("hashchange", route);
window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    const saveButton = $("#save-file");
    if (saveButton) saveButton.click();
  }
  if (event.key === "Escape") {
    const dialog = $("#confirm-dialog");
    if (dialog.open) dialog.close("cancel");
    $(".sidebar").classList.remove("open");
  }
});

async function loadSkills() {
  const data = await api("/api/skills");
  state.skills = data.skills;
  state.categories = [...new Set(data.skills.map((skill) => skill.category))].sort();
}

async function renderHome() {
  setTitle("Library", "Skills");
  view.innerHTML = `<div class="toolbar">
    <div class="filters">
      <input id="search" type="search" placeholder="Search by name or category" aria-label="Search skills" />
      <select id="category-filter" aria-label="Filter category">
        <option value="">All categories</option>
      </select>
    </div>
    <span class="muted" id="skill-count"></span>
  </div>
  <div id="skills-grid" class="grid"></div>`;
  await loadSkills();
  const categoryFilter = $("#category-filter");
  state.categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    categoryFilter.append(option);
  });
  $("#search").addEventListener("input", drawSkillCards);
  categoryFilter.addEventListener("change", drawSkillCards);
  drawSkillCards();
}

function drawSkillCards() {
  const query = $("#search").value.toLowerCase();
  const category = $("#category-filter").value;
  const filtered = state.skills.filter((skill) => {
    const matchesQuery = `${skill.name} ${skill.category}`.toLowerCase().includes(query);
    return matchesQuery && (!category || skill.category === category);
  });
  $("#skill-count").textContent = `${filtered.length} skill${filtered.length === 1 ? "" : "s"}`;
  const grid = $("#skills-grid");
  grid.innerHTML = "";
  if (!filtered.length) {
    grid.innerHTML = `<section class="panel"><h2>No skills found</h2><p class="muted">Adjust the search or category filter.</p></section>`;
    return;
  }
  filtered.forEach((skill) => {
    const card = document.createElement("a");
    card.className = "card";
    card.href = `#/skill/${encodeURIComponent(skill.id)}`;
    card.innerHTML = `<div>
      <div class="meta"><span class="chip">${escapeHtml(skill.category)}</span>${skill.single_file ? '<span class="chip">single file</span>' : ""}</div>
      <h2>${escapeHtml(skill.name)}</h2>
      <p class="muted">${escapeHtml(skill.description || "No description in SKILL.md frontmatter.")}</p>
    </div>
    <div class="meta"><span>Modified ${formatDate(skill.modified)}</span></div>`;
    grid.append(card);
  });
}

async function renderSkill(skillId) {
  const data = await api(`/api/skills/${encodeURIComponent(skillId)}`);
  state.currentSkill = data.skill;
  setTitle(data.skill?.category || "Skill", data.skill?.name || skillId);
  view.innerHTML = `<div class="toolbar">
    <div class="actions">
      <a class="ghost" href="#/">Back</a>
      <a class="primary" href="${appUrl(`/api/download/skill/${encodeURIComponent(skillId)}`)}">Download skill</a>
      ${data.skill ? `<a class="ghost" href="${appUrl(`/api/download/category/${encodeURIComponent(data.skill.category)}`)}">Download category</a>` : ""}
    </div>
    <div class="meta"><span>${data.skill?.single_file ? "Single markdown file" : "Skill directory"}</span></div>
  </div>
  <div class="detail-layout">
    <section class="panel">
      <h2>Files</h2>
      <div class="meta"><span>Size ${formatBytes(data.tree.size)}</span><span>Modified ${formatDate(data.tree.modified)}</span></div>
      <ul id="file-tree" class="tree"></ul>
    </section>
    <section id="file-panel" class="file-viewer">
      <div class="file-body"><p class="muted">Select a file to view or edit it.</p></div>
    </section>
  </div>`;
  const tree = $("#file-tree");
  const root = data.tree.type === "file" ? data.tree : data.tree.children.find((child) => child.name === "SKILL.md") || data.tree.children[0];
  drawTree(tree, data.tree, skillId);
  if (root && root.type === "file") openFile(skillId, root.path);
}

function drawTree(container, node, skillId) {
  const li = document.createElement("li");
  if (node.type === "file") {
    const button = document.createElement("button");
    button.className = "ghost";
    button.type = "button";
    button.textContent = node.name;
    button.dataset.path = node.path;
    button.addEventListener("click", () => openFile(skillId, node.path));
    li.append(button);
  } else {
    const title = document.createElement("p");
    title.className = "muted";
    title.textContent = node.name;
    li.append(title);
    const ul = document.createElement("ul");
    (node.children || []).forEach((child) => drawTree(ul, child, skillId));
    li.append(ul);
  }
  container.append(li);
}

async function openFile(skillId, filePath) {
  document.querySelectorAll(".tree button").forEach((button) => button.classList.toggle("active", button.dataset.path === filePath));
  const file = await api(`/api/files/${encodeURIComponent(skillId)}?path=${encodeURIComponent(filePath)}`);
  state.selectedFile = { skillId, filePath, file };
  state.editorDirty = false;
  const panel = $("#file-panel");
  const editable = !file.binary && isEditable(file.name);
  panel.innerHTML = `<div class="file-header">
    <div>
      <h2>${escapeHtml(file.name)} <span id="dirty-indicator" class="dirty" hidden>unsaved</span></h2>
      <div class="meta"><span>${formatBytes(file.size)}</span><span>Modified ${formatDate(file.modified)}</span></div>
    </div>
    <div class="actions">
      ${file.name.endsWith(".md") && !file.binary ? '<button id="toggle-markdown" class="ghost" type="button">Raw source</button>' : ""}
      ${editable ? '<button id="edit-file" class="ghost" type="button">Edit</button><button id="save-file" class="primary" type="button" hidden>Save</button>' : ""}
      <a class="ghost" href="${appUrl(`/api/download/file/${encodeURIComponent(skillId)}?path=${encodeURIComponent(filePath)}`)}">Download</a>
    </div>
  </div>
  <div id="file-body" class="file-body"></div>`;
  renderFileBody(false);
  $("#toggle-markdown")?.addEventListener("click", (event) => {
    const raw = event.currentTarget.textContent === "Rendered";
    event.currentTarget.textContent = raw ? "Raw source" : "Rendered";
    renderFileBody(!raw);
  });
  $("#edit-file")?.addEventListener("click", startEditing);
  $("#save-file")?.addEventListener("click", saveFile);
}

function renderFileBody(raw = false) {
  const { file } = state.selectedFile;
  const body = $("#file-body");
  if (file.binary) {
    if (file.mime.startsWith("image/")) {
      body.innerHTML = `<img alt="${escapeHtml(file.name)}" src="${appUrl(`/api/download/file/${encodeURIComponent(state.selectedFile.skillId)}?path=${encodeURIComponent(state.selectedFile.filePath)}`)}" style="max-width:100%;height:auto;border-radius:8px" />`;
    } else {
      body.innerHTML = `<p class="muted">Binary file. Download to view.</p>`;
    }
    return;
  }
  if (file.name.endsWith(".md") && !raw && window.marked) {
    body.innerHTML = `<article class="markdown">${marked.parse(file.content)}</article>`;
    return;
  }
  const language = file.name.split(".").pop();
  const escaped = escapeHtml(file.content);
  body.innerHTML = `<pre><code class="language-${language}">${escaped}</code></pre>`;
  if (window.hljs) body.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
}

function startEditing() {
  const { file } = state.selectedFile;
  $("#file-body").innerHTML = `<textarea id="editor" class="editor" spellcheck="false">${escapeHtml(file.content)}</textarea>`;
  $("#edit-file").hidden = true;
  $("#save-file").hidden = false;
  $("#editor").focus();
  $("#editor").addEventListener("input", () => {
    state.editorDirty = true;
    $("#dirty-indicator").hidden = false;
  });
}

async function saveFile() {
  const editor = $("#editor");
  if (!editor) return;
  const dialog = $("#confirm-dialog");
  dialog.showModal();
  const result = await new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue), { once: true });
  });
  if (result !== "confirm") return;
  const { skillId, filePath } = state.selectedFile;
  const file = await api(`/api/files/${encodeURIComponent(skillId)}?path=${encodeURIComponent(filePath)}`, {
    method: "PUT",
    body: JSON.stringify({ content: editor.value }),
  });
  state.selectedFile.file = file;
  state.editorDirty = false;
  toast("File saved");
  await openFile(skillId, filePath);
}

function renderUpload() {
  setTitle("Incoming", "Upload");
  view.innerHTML = `<section class="dropzone" id="dropzone">
    <div class="stack">
      <h2>Drop a .md or .zip file</h2>
      <p class="muted">Markdown files are saved into incoming. Zip files are extracted into incoming using a sanitized folder name.</p>
      <input id="upload-input" type="file" accept=".md,.zip" />
      <progress id="upload-progress" value="0" max="100" hidden></progress>
      <p id="upload-status" class="muted"></p>
    </div>
  </section>`;
  const input = $("#upload-input");
  const zone = $("#dropzone");
  input.addEventListener("change", () => input.files[0] && uploadFile(input.files[0]));
  ["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.add("dragover");
  }));
  ["dragleave", "drop"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.remove("dragover");
  }));
  zone.addEventListener("drop", (event) => {
    const file = event.dataTransfer.files[0];
    if (file) uploadFile(file);
  });
}

async function uploadFile(file) {
  if (!file.name.endsWith(".md") && !file.name.endsWith(".zip")) {
    $("#upload-status").textContent = "Only .md and .zip uploads are supported.";
    return;
  }
  const progress = $("#upload-progress");
  progress.hidden = false;
  progress.value = 35;
  const data = new FormData();
  data.append("file", file);
  try {
    const result = await api("/api/upload", { method: "POST", body: data });
    progress.value = 100;
    $("#upload-status").innerHTML = `Uploaded to <strong>${escapeHtml(result.path)}</strong>.`;
    toast("Upload complete");
  } catch (error) {
    $("#upload-status").textContent = error.message;
  }
}

function renderSettings() {
  setTitle("Account", "Settings");
  view.innerHTML = `<section class="panel stack">
    <h2>Change password</h2>
    <form id="password-form" class="stack">
      <label>Current password<input name="current_password" type="password" autocomplete="current-password" required /></label>
      <label>New password<input name="new_password" type="password" autocomplete="new-password" minlength="8" required /></label>
      <button class="primary" type="submit">Update password</button>
      <p id="password-status" class="muted"></p>
    </form>
  </section>`;
  $("#password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form));
    try {
      await api("/api/auth/password", { method: "POST", body: JSON.stringify(payload) });
      $("#password-status").textContent = "Password updated.";
      toast("Password changed");
      form.reset();
    } catch (error) {
      $("#password-status").textContent = error.message;
    }
  });
}

function isEditable(name) {
  return /\.(md|ya?ml|txt|json|toml|py|sh|js|ts|css|html|xml|ini|conf|env)$/i.test(name);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value) {
  return new Date(value).toLocaleString();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

boot().catch((error) => {
  console.error(error);
  $("#app-shell").hidden = true;
  showLogin();
});
