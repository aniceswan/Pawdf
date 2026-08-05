/* Pawdf UI. Plain JavaScript, no framework and no build step.
 *
 * The flow is: add files, then pick what to do with them. That ordering is
 * the whole design. It means a tool never has to ask "which file?" -- the
 * answer is already on screen -- and it means the ring can show you, before
 * you click anything, which tools can actually open what you added.
 *
 * Every path here came from a native dialog or a native drop (gui/dnd.py).
 * Every operation runs on a Python worker thread and answers over a signal.
 */

"use strict";

let bridge = null;

/* Tool glyphs, keyed by the feature ids in core/registry.py. The ring itself
   is built from Python data; only the artwork lives here. */
const ICONS = {
  split:
    '<circle cx="6" cy="6" r="2.6"/><circle cx="6" cy="18" r="2.6"/><path d="M8.2 7.6L20 18M8.2 16.4L20 6"/>',
  merge:
    '<path d="M4 5h3a4 4 0 0 1 4 4v6a4 4 0 0 0 4 4h4"/><path d="M4 19h3a4 4 0 0 0 4-4"/><path d="M16 16l3 3-3 3"/>',
  organize:
    '<rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/>',
  compress: '<path d="M4 12h16"/><path d="M9 7l3-3 3 3"/><path d="M9 17l3 3 3-3"/><path d="M12 4v4M12 16v4"/>',
  ocr:
    '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M8 11h8M8 14.5h5"/>',
  rasterize:
    '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="M20 16l-4.5-4.5L7 20"/>',
  imagepdf:
    '<rect x="8" y="3" width="13" height="10" rx="1.8"/><circle cx="12" cy="6.6" r="1.1"/><path d="M21 10.5l-3.5-3L11 13"/><path d="M16 17H5a1.5 1.5 0 0 1-1.5-1.5V7"/><path d="M7 14.5l-3.5 3 3.5 3"/>',
  pdf_to_docx: '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/><path d="M8.6 12l1.5 5 1.9-5 1.9 5 1.5-5"/>',
  rotate:
    '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v5h-5"/>',
  crop:
    '<path d="M6 2v16h16"/><path d="M2 6h16v16"/>',
  repair:
    '<path d="M14.7 6.3a4 4 0 0 0 5.3 5.3L21 21H3l8.4-8.4a4 4 0 0 0 3.3-6.3z"/><path d="M14.7 6.3L18 3"/>',
  protect:
    '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/><circle cx="12" cy="15.2" r="1.3"/>',
  unlock:
    '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 7.5-1.9"/><circle cx="12" cy="15.2" r="1.3"/>',
  watermark:
    '<path d="M12 3l6.5 6.5a9 9 0 1 1-13 0z"/><path d="M8.5 14.5h7"/>',
  sign:
    '<path d="M3 17c3-6 6 3 9-3s6 1 9-4"/><path d="M4 21h16"/>',
  forms:
    '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h4"/>',
  annotate:
    '<path d="M15.5 4.5l4 4L9 19l-5 1 1-5z"/><path d="M4 21h16"/>',
  pagenumbers:
    '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 17h3"/><path d="M9.5 17v-3l-1.5.9"/>',
  pdf_to_markdown:
    '<path d="M3 6h18v12H3z"/><path d="M6 15V9l2.5 3L11 9v6"/><path d="M15 9v6M15 15l2.5-2.5M15 15l-2.5-2.5"/>',
  xlsx_to_pdf:
    '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/><path d="M9 12l5 6M14 12l-5 6"/>',
  pptx_to_pdf:
    '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/><path d="M9 19v-7h2.4a2 2 0 0 1 0 4H9"/>',
  docx_to_pdf:
    '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/><path d="M9 12.5h2.2a1.6 1.6 0 0 1 0 3.2H9V12.5zM9 15.7V19"/><path d="M13.5 19v-6.5h1.6a2.2 2.2 0 0 1 0 6.5z"/>',
};

/* One glyph per category, for the first ring. */
const CATEGORY_ICONS = {
  organise:
    '<rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><path d="M14 17.2h7M17.5 13.7v7"/>',
  convert:
    '<path d="M4 8h12l-3-3M20 16H8l3 3"/>',
  optimise:
    '<path d="M12 3v4M12 17v4M4 12h4M16 12h4"/><circle cx="12" cy="12" r="4"/>',
  secure:
    '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
  annotate:
    '<path d="M4 20h16"/><path d="M15.5 4.5l4 4L9 19l-5 1 1-5z"/>',
};

/* Tools that consume the whole selection rather than one file. */
const MULTI_FILE_TOOLS = new Set(["merge", "imagepdf"]);

/* ------------------------------------------------------------- helpers -- */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const baseName = (path) => String(path).split(/[\\/]/).pop();

function extensionOf(path) {
  const name = baseName(path);
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

function humanSize(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let n = Number(bytes) || 0;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return (i === 0 ? Math.round(n) : n.toFixed(1)) + " " + units[i];
}

/** Percentage saved, guarding the empty-input case that would give NaN. */
function percentSaved(originalSize, compressedSize) {
  if (!originalSize || originalSize <= 0) return null;
  return Math.round(100 * (1 - compressedSize / originalSize));
}

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

/* --------------------------------------------------------------- toast -- */

let toastTimer = null;

function showToast(kind, title, message, action) {
  const el = $("#toast");
  el.className = kind;
  el.textContent = "";

  const titleEl = document.createElement("div");
  titleEl.className = "toast-title";
  titleEl.textContent = title;

  const bodyEl = document.createElement("div");
  bodyEl.className = "toast-body";
  bodyEl.textContent = message;

  el.append(titleEl, bodyEl);

  if (action) {
    const btn = document.createElement("button");
    btn.className = "toast-action";
    btn.textContent = action.label;
    btn.addEventListener("click", () => {
      action.run();
      el.classList.remove("show");
    });
    el.appendChild(btn);
  }

  requestAnimationFrame(() => el.classList.add("show"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), action ? 8000 : 5000);
}

const reveal = (path) => ({ label: "Show in folder", run: () => bridge.revealPath(path) });

/* --------------------------------------------------------------- theme -- */

const THEME_KEY = "pawdf-theme";

const SESSION_KEY = "pawdf-session-v1";

function persistSession() {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session.files));
  } catch (err) {
    /* Session recovery is a convenience; file operations never depend on it. */
  }
}

function restoreSession() {
  let saved;
  try {
    saved = JSON.parse(localStorage.getItem(SESSION_KEY) || "[]");
  } catch (err) {
    saved = [];
  }
  if (!Array.isArray(saved) || !saved.length) return;

  bridge.existingFiles(JSON.stringify(saved), (json) => {
    const existing = JSON.parse(json);
    if (!Array.isArray(existing)) return;
    session.files = existing;
    persistSession();
    renderFiles();
    renderRing();
  });
}

function forgetRememberedSession() {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch (err) {
    /* Nothing else to clear. */
  }
  clearFiles();
  showToast("success", "Session", "Remembered files were forgotten.");
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch (err) {
    /* A file:// page may have storage disabled; the theme just won't persist. */
  }
}

const toggleTheme = () =>
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

/* ==========================================================================
   State
   ========================================================================== */

const features = new Map();
const categories = new Map();

/** The one selection every tool draws from. */
const session = {
  files: [],
  tool: null,
  /** null at the top level, otherwise the category whose tools are showing. */
  category: null,
};

const organize = { source: null, pages: [] };
let signatureImage = null;

const accepts = (featureId, ext) => {
  const feature = features.get(featureId);
  return !!feature && feature.accepts.includes(ext);
};

/** The files a given tool would actually operate on. */
function filesFor(featureId) {
  const feature = features.get(featureId);
  if (!feature) return [];
  const usable = session.files.filter((p) => feature.accepts.includes(extensionOf(p)));
  return MULTI_FILE_TOOLS.has(featureId) ? usable : usable.slice(0, 1);
}

const canRun = (featureId) => filesFor(featureId).length > 0;

const featuresIn = (categoryId) =>
  Array.from(features.values()).filter((f) => f.category === categoryId);

/** How many tools in a category can open what is currently in the tray. */
const usableIn = (categoryId) => featuresIn(categoryId).filter((f) => canRun(f.id)).length;

/* ==========================================================================
   Files
   ========================================================================== */

function addFiles(paths) {
  const fresh = paths.filter((p) => !session.files.includes(p));
  if (!fresh.length) {
    if (paths.length) showToast("error", "Files", "Those are already in the list.");
    return;
  }
  session.files.push(...fresh);
  persistSession();
  renderFiles();
  renderRing();

  // Adding a file while a tool is open should update that tool, not silently
  // sit in the tray behind it.
  if (session.tool) syncActiveTool();
}

function removeFile(index) {
  session.files.splice(index, 1);
  persistSession();
  renderFiles();
  renderRing();
  if (session.tool) syncActiveTool();
}

function clearFiles() {
  session.files = [];
  persistSession();
  organize.source = null;
  organize.pages = [];
  renderFiles();
  renderRing();
  if (session.tool) closeTool();
}

function moveFile(from, to) {
  if (to < 0 || to >= session.files.length) return;
  const [moved] = session.files.splice(from, 1);
  session.files.splice(to, 0, moved);
  persistSession();
  renderFiles();
  if (session.tool) syncActiveTool();
}

function renderFiles() {
  const items = $("#tray-items");
  document.body.classList.toggle("empty", session.files.length === 0);
  $(".tray-count").textContent = plural(session.files.length, "file") + " ready";

  items.textContent = "";
  session.files.forEach((path, i) => {
    const row = document.createElement("div");
    row.className = "file-row";

    const index = document.createElement("span");
    index.className = "file-index";
    index.textContent = String(i + 1);

    const kind = document.createElement("span");
    kind.className = "file-kind";
    kind.textContent = (extensionOf(path) || "?").replace(".", "").toUpperCase();

    const name = document.createElement("span");
    name.className = "file-name";
    name.textContent = baseName(path);
    name.title = path;

    row.append(index, kind, name);

    const mk = (glyph, title, disabled, onClick, extra = "") => {
      const b = document.createElement("button");
      b.className = `file-btn ${extra}`;
      b.textContent = glyph;
      b.title = title;
      b.disabled = disabled;
      b.addEventListener("click", onClick);
      return b;
    };

    // Order matters for Merge and Images to PDF, so it is editable here
    // rather than duplicated inside each of those tools.
    row.append(
      mk("↑", "Move up", i === 0, () => moveFile(i, i - 1)),
      mk("↓", "Move down", i === session.files.length - 1, () => moveFile(i, i + 1)),
      mk("✕", "Remove", false, () => removeFile(i), "remove")
    );

    items.appendChild(row);
  });
}

/* ==========================================================================
   The ring
   ========================================================================== */

function ringRadius() {
  const raw = getComputedStyle(document.documentElement).getPropertyValue("--ring-radius");
  return parseFloat(raw) || 232;
}

function cssPx(name, fallback) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name);
  return parseFloat(raw) || fallback;
}

const nodeSize = () => cssPx("--node", 116);
const hubSize = () => cssPx("--hub", 132);

/** Place `nodes` evenly around the ring, starting at the top, clockwise.
 *
 * The radius shrinks when there are few nodes. Three tools on a ring sized
 * for eight reads as three things that drifted apart, not as a menu, so the
 * circle is only ever as big as its contents need.
 */
function layoutRing(nodes) {
  const container = $("#ring-nodes");
  container.textContent = "";

  // The ring rotates and every node counter-rotates to stay upright. Those
  // are two animations that only cancel out while they agree on the time.
  // The container's has been running since load; the nodes are built fresh on
  // every ring change, so theirs start at zero and the difference shows up as
  // permanently tilted tiles. Restarting the container's animation here puts
  // both back at zero together.
  container.style.animation = "none";
  void container.offsetWidth; // force the style change to take effect
  container.style.animation = "";

  const maxRadius = ringRadius();
  const size = nodeSize();

  // Enough circumference for every node plus a gap of a third of a node...
  const needed = (nodes.length * size * 1.34) / (2 * Math.PI);
  // ...but never so tight that a node sits on top of the hub. With two tools
  // in a category the circumference calculation alone puts them right through
  // the middle, so the floor is "clear of the hub", not "clear of each other".
  const floor = hubSize() / 2 + size / 2 + 18;
  const radius = Math.max(floor, Math.min(maxRadius, needed));
  $("#ring").style.setProperty("--used-radius", `${radius}px`);
  nodes.forEach((node, i) => {
    const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;

    // Three nested elements, each owning exactly one transform, because they
    // would otherwise overwrite one another:
    //   .slot     position on the ring + the entrance animation
    //   .upright  counter-rotation, so an orbiting node stays readable
    //   .node     hover lift
    const slot = document.createElement("div");
    slot.className = "slot";
    slot.style.setProperty("--i", String(i));
    slot.style.setProperty("--x", `${Math.cos(angle) * radius}px`);
    slot.style.setProperty("--y", `${Math.sin(angle) * radius}px`);

    const upright = document.createElement("div");
    upright.className = "upright";
    upright.appendChild(node);
    slot.appendChild(upright);
    container.appendChild(slot);
  });
}

function categoryNode(category) {
  const node = document.createElement("button");
  node.className = "node node-category";
  node.dataset.category = category.id;
  node.style.setProperty("--node-hue", String(category.hue));
  node.title = category.tagline;

  const usable = usableIn(category.id);
  const total = featuresIn(category.id).length;

  node.innerHTML =
    `<svg class="node-icon" viewBox="0 0 24 24">${CATEGORY_ICONS[category.id] || ""}</svg>` +
    `<span class="node-label"></span><span class="node-meta"></span>`;
  $(".node-label", node).textContent = category.title;
  $(".node-meta", node).textContent = session.files.length
    ? `${usable} of ${total} ready`
    : plural(total, "tool");

  // A category is dead only if none of its tools can take what is loaded.
  node.disabled = session.files.length > 0 && usable === 0;
  node.addEventListener("click", () => openCategory(category.id));
  return node;
}

function toolNode(feature) {
  const node = document.createElement("button");
  node.className = "node";
  node.dataset.feature = feature.id;
  node.style.setProperty("--node-hue", String(feature.hue));

  const usable = canRun(feature.id);
  node.disabled = !usable;
  node.title = usable
    ? feature.tagline
    : session.files.length === 0
      ? "Add a file first"
      : `Needs ${feature.accepts.join(" or ")}`;

  node.innerHTML =
    `<svg class="node-icon" viewBox="0 0 24 24">${ICONS[feature.id] || ""}</svg>` +
    `<span class="node-label"></span>`;
  $(".node-label", node).textContent = feature.title;
  node.addEventListener("click", () => openTool(feature.id));
  return node;
}

/** Redraw whichever ring level is current. */
function renderRing() {
  const atTop = session.category === null;
  document.body.classList.toggle("in-category", !atTop);

  const hubLabel = $("#hub-caption");
  const hub = $("#hub");
  if (atTop) {
    layoutRing(Array.from(categories.values()).map(categoryNode));
    hubLabel.textContent = "Add files";
    hub.setAttribute("aria-label", "Add files");
    $("#ring-title").textContent = "";
  } else {
    const category = categories.get(session.category);
    layoutRing(featuresIn(session.category).map(toolNode));
    hubLabel.textContent = "Back";
    hub.setAttribute("aria-label", "Back to all categories");
    $("#ring-title").textContent = category ? category.title : "";
  }

  $$(".node[data-feature]").forEach((n) =>
    n.classList.toggle("selected", session.tool === n.dataset.feature)
  );
}

function openCategory(categoryId) {
  session.category = categoryId;
  renderRing();
}

function leaveCategory() {
  session.category = null;
  renderRing();
}

/** The hub does two jobs, depending on which ring you are looking at. */
function hubPressed() {
  if (session.category === null) promptForFiles();
  else leaveCategory();
}

/* ==========================================================================
   Tool search

   The ring is good at "show me what this app can do" and bad at "open the
   watermark tool now". This is the second one.
   ========================================================================== */

let searchIndex = -1;

function openSearch() {
  const box = $("#search");
  box.hidden = false;
  $("#search-input").value = "";
  renderSearch("");
  requestAnimationFrame(() => {
    box.classList.add("show");
    $("#search-input").focus();
  });
}

function closeSearch() {
  const box = $("#search");
  box.classList.remove("show");
  searchIndex = -1;
  setTimeout(() => {
    if (!box.classList.contains("show")) box.hidden = true;
  }, 180);
}

function searchMatches(query) {
  const q = query.trim().toLowerCase();
  const all = Array.from(features.values());
  if (!q) return all;
  return all.filter((f) => {
    const haystack = `${f.title} ${f.tagline} ${f.category}`.toLowerCase();
    return haystack.includes(q);
  });
}

function renderSearch(query) {
  const list = $("#search-results");
  const matches = searchMatches(query);
  searchIndex = matches.length ? 0 : -1;

  list.textContent = "";
  if (!matches.length) {
    const empty = document.createElement("div");
    empty.className = "search-empty";
    empty.textContent = "No tool matches that.";
    list.appendChild(empty);
    return;
  }

  matches.forEach((feature, i) => {
    const row = document.createElement("button");
    row.className = "search-row" + (i === 0 ? " active" : "");
    row.dataset.feature = feature.id;
    row.style.setProperty("--node-hue", String(feature.hue));

    const usable = canRun(feature.id);
    row.innerHTML =
      `<svg class="search-icon" viewBox="0 0 24 24">${ICONS[feature.id] || ""}</svg>` +
      `<span class="search-text"><span class="search-title"></span>` +
      `<span class="search-sub"></span></span>`;
    $(".search-title", row).textContent = feature.title;
    $(".search-sub", row).textContent = usable
      ? feature.tagline
      : `Needs ${feature.accepts.join(" or ")}`;
    row.classList.toggle("unavailable", !usable);

    row.addEventListener("click", () => {
      closeSearch();
      openCategory(feature.category);
      openTool(feature.id);
    });
    list.appendChild(row);
  });
}

function moveSearch(delta) {
  const rows = $$("#search-results .search-row");
  if (!rows.length) return;
  searchIndex = (searchIndex + delta + rows.length) % rows.length;
  rows.forEach((r, i) => r.classList.toggle("active", i === searchIndex));
  rows[searchIndex].scrollIntoView({ block: "nearest" });
}

function commitSearch() {
  const rows = $$("#search-results .search-row");
  if (searchIndex >= 0 && rows[searchIndex]) rows[searchIndex].click();
}

/* ==========================================================================
   Tool navigation
   ========================================================================== */

function openTool(featureId) {
  if (featureId !== "settings" && !canRun(featureId)) {
    showToast(
      "error",
      features.get(featureId).title,
      session.files.length === 0
        ? "Add a file first - press the + in the middle."
        : `Nothing in your list is a ${features.get(featureId).accepts.join(" or ")} file.`
    );
    return;
  }

  session.tool = featureId;
  const feature = features.get(featureId);
  // Opening from search jumps straight to a tool, so make sure the ring
  // behind it is showing that tool's category rather than the top level.
  if (feature && session.category !== feature.category) session.category = feature.category;

  $("#detail-title").textContent = feature ? feature.title : "Settings";
  $("#detail-tagline").textContent = feature ? feature.tagline : "Ghostscript, theme, and privacy";

  $$(".panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === featureId));
  document.body.classList.add("tool-open");

  if (featureId === "settings") {
    refreshGhostscript();
    refreshTesseract();
    refreshDiagnostics();
  }
  if (featureId === "ocr") refreshTesseract();
  syncActiveTool();
  renderRing();
}

function closeTool() {
  document.body.classList.remove("tool-open");
  session.tool = null;
  previewPath = null;
  closeLightbox();
  renderRing();
}

/** Point the open tool at the current selection. */
function syncActiveTool() {
  const id = session.tool;
  if (!id) return;

  const box = $("#detail-files");
  if (id === "settings") {
    box.hidden = true;
    return;
  }
  box.hidden = false;

  const files = filesFor(id);
  box.classList.toggle("warn", files.length === 0);
  box.textContent = "";

  const label = document.createElement("span");
  label.className = "df-label";
  const name = document.createElement("span");
  name.className = "df-name";

  if (!files.length) {
    label.textContent = "Nothing to work on";
    name.textContent = `Add a ${features.get(id).accepts.join(" or ")} file.`;
  } else if (MULTI_FILE_TOOLS.has(id)) {
    label.textContent = `Using ${plural(files.length, "file")}, in this order`;
    name.textContent = files.map(baseName).join("  ·  ");
  } else {
    label.textContent = "Working on";
    name.textContent = baseName(files[0]);
    name.title = files[0];
  }
  box.append(label, name);

  const runBtn = $(`.run-btn[data-run="${id}"]`);
  if (runBtn) runBtn.disabled = files.length === 0;

  if (id === "organize" && files.length && organize.source !== files[0]) {
    loadPages(files[0]);
  }
  if (id === "forms" && files.length) loadFormFields(files[0]);
  if (id === "unlock" && files.length) {
    bridge.isEncrypted(files[0], (locked) => {
      $("#unlock-note").textContent = locked
        ? "This file is encrypted. Enter its password to remove the lock."
        : "This file has no password, so there is nothing to remove.";
    });
  }
  showPreview(id, files[0] || null);
}

/** Build one input per field in the document, since a form's shape is
    whatever the document says it is. */
function loadFormFields(path) {
  const host = $("#form-fields");
  host.textContent = "Reading fields...";

  bridge.formFields(path, (json) => {
    let fields = [];
    try {
      fields = JSON.parse(json);
    } catch (error) {
      host.textContent = "Pawdf could not read this form.";
      return;
    }
    host.textContent = "";

    if (!fields.length) {
      const empty = document.createElement("p");
      empty.className = "notice";
      empty.textContent =
        "This PDF has no interactive form. Only forms built with fillable " +
        "fields can be filled in; a scan or a printed form cannot.";
      host.appendChild(empty);
      return;
    }

    for (const field of fields) {
      if (field.read_only || ["signature", "pushbutton", "unknown"].includes(field.kind)) {
        const unsupported = document.createElement("div");
        unsupported.className = "form-field-unsupported";
        unsupported.textContent =
          `${field.name}: ${field.kind} fields cannot be edited safely in Pawdf.`;
        host.appendChild(unsupported);
        continue;
      }

      const wrapper = document.createElement("label");
      wrapper.className = field.kind === "checkbox" ? "check" : "field";

      if (field.kind === "checkbox") {
        const input = document.createElement("input");
        input.type = "checkbox";
        input.dataset.field = field.name;
        input.checked = Boolean(field.value && field.value !== "/Off");
        const label = document.createElement("span");
        label.textContent = field.name;
        wrapper.append(input, label);
      } else if (field.kind === "radio" || field.kind === "choice") {
        const label = document.createElement("span");
        label.className = "field-label";
        label.textContent = field.name;

        const select = document.createElement("select");
        select.dataset.field = field.name;
        const options = field.kind === "radio"
          ? field.options.filter((raw) => raw !== "/Off")
          : field.options;

        if (field.kind === "radio") {
          const blank = document.createElement("option");
          blank.value = "/Off";
          blank.textContent = "No selection";
          select.appendChild(blank);
        }

        for (const raw of options) {
          const option = document.createElement("option");
          option.value = raw;
          option.textContent = String(raw).replace(/^\//, "");
          select.appendChild(option);
        }
        select.value = field.value || (field.kind === "radio" ? "/Off" : "");
        wrapper.append(label, select);
      } else {
        const label = document.createElement("span");
        label.className = "field-label";
        label.textContent = field.name;
        const input = document.createElement("input");
        input.type = "text";
        input.dataset.field = field.name;
        input.value = field.value || "";
        wrapper.append(label, input);
      }
      host.appendChild(wrapper);
    }
  });
}

/* ==========================================================================
   Page thumbnails

   One store, shared by the preview strip and the Arrange grid. Rendering a
   page costs real time, so a document is rendered once and both consumers
   read the same pages; switching between tools no longer re-renders anything.
   ========================================================================== */

const documents = new Map(); // path -> { count, pages, ready, listeners }

function pagesOf(path, listener) {
  let doc = documents.get(path);
  if (doc) {
    if (listener) {
      doc.listeners.add(listener);
      listener(doc);
    }
    return doc;
  }

  doc = { count: 0, pages: [], ready: false, failed: false, listeners: new Set() };
  if (listener) doc.listeners.add(listener);
  documents.set(path, doc);

  bridge.pageCount(path, (count) => {
    if (!count) {
      doc.failed = true;
      doc.ready = true;
      notify(doc);
      return;
    }
    doc.count = count;
    doc.pages = Array.from({ length: count }, (_, i) => ({
      index: i,
      dataUrl: null,
      error: "",
      settled: false,
    }));
    notify(doc);
    for (let i = 0; i < count; i += 1) bridge.requestThumbnail(path, i);
  });

  return doc;
}

const notify = (doc) => doc.listeners.forEach((fn) => fn(doc));

function onThumbnail(payload) {
  const doc = documents.get(payload.path);
  if (!doc) return;
  const page = doc.pages[payload.index];
  if (!page || page.settled) return;

  page.dataUrl = payload.dataUrl || null;
  page.error = payload.error || "";
  page.settled = true;

  // Every request answers, success or failure, so this always completes: one
  // page that throws can't leave the view loading forever.
  doc.ready = doc.pages.every((p) => p.settled);
  notify(doc);
}

/* ==========================================================================
   Preview

   Answers "which page was that again?" without making anyone open the PDF in
   another application first. Split leans on it hardest: picking ranges from
   memory is guesswork, so there clicking a page builds the range for you.
   ========================================================================== */

/** Tools that take exactly one PDF, and so have something to preview. */
function hasPreview(featureId) {
  const feature = features.get(featureId);
  if (!feature || featureId === "organize") return false; // Arrange has its own grid
  return feature.accepts.includes(".pdf") && !MULTI_FILE_TOOLS.has(featureId);
}

const splitSelection = new Set();

/** [0,1,2,4,7,8] -> "1-3, 5, 8-9" */
function rangesFromSelection(selected) {
  const sorted = [...selected].sort((a, b) => a - b);
  const parts = [];
  let run = null;
  for (const page of sorted) {
    if (run && page === run.end + 1) {
      run.end = page;
      continue;
    }
    if (run) parts.push(run);
    run = { start: page, end: page };
  }
  if (run) parts.push(run);
  return parts
    .map((r) => (r.start === r.end ? `${r.start + 1}` : `${r.start + 1}-${r.end + 1}`))
    .join(", ");
}

/** "1-3, 5" -> Set{0,1,2,4}. Anything unparseable is ignored, not rejected:
    this only drives highlighting, and the real parsing happens in Python. */
function selectionFromRanges(text, count) {
  const selected = new Set();
  for (const chunk of String(text).split(",")) {
    const piece = chunk.trim();
    if (!piece) continue;
    const [a, b] = piece.split("-").map((n) => parseInt(n, 10));
    const from = Number.isFinite(a) ? a : NaN;
    const to = piece.includes("-") ? (Number.isFinite(b) ? b : NaN) : from;
    if (!Number.isFinite(from) || !Number.isFinite(to)) continue;
    for (let i = Math.max(from, 1); i <= Math.min(to, count); i += 1) selected.add(i - 1);
  }
  return selected;
}

let previewPath = null;

function showPreview(featureId, path) {
  const wrap = $("#preview");
  if (!hasPreview(featureId) || !path) {
    wrap.hidden = true;
    previewPath = null;
    return;
  }

  wrap.hidden = false;
  previewPath = path;
  const grid = $("#preview-grid");
  const isSplit = featureId === "split";
  $("#preview-hint").textContent = isSplit
    ? "Click pages to build the ranges below."
    : "Click a page to see it larger.";

  if (isSplit) {
    splitSelection.clear();
    selectionFromRanges($("#split-ranges").value, 9999).forEach((i) => splitSelection.add(i));
  }

  grid.textContent = "";
  const status = document.createElement("div");
  status.className = "grid-status";
  status.textContent = "Reading document...";
  grid.appendChild(status);

  pagesOf(path, function render(doc) {
    if (previewPath !== path) return;

    if (doc.failed) {
      status.textContent = "That PDF couldn't be opened.";
      return;
    }
    if (!doc.count) return;

    $("#preview-count").textContent = plural(doc.count, "page");
    grid.textContent = "";

    doc.pages.forEach((page) => {
      const cell = document.createElement("button");
      cell.className = "pv-page";
      if (isSplit && splitSelection.has(page.index)) cell.classList.add("picked");

      if (page.dataUrl) {
        const img = document.createElement("img");
        img.src = page.dataUrl;
        img.alt = "";
        cell.appendChild(img);
      } else {
        const ph = document.createElement("div");
        ph.className = "pv-placeholder";
        ph.textContent = page.settled ? "!" : "";
        cell.appendChild(ph);
      }

      const num = document.createElement("span");
      num.className = "pv-num";
      num.textContent = String(page.index + 1);
      cell.appendChild(num);

      cell.addEventListener("click", () => {
        if (!isSplit) return openLightbox(path, page.index);
        if (splitSelection.has(page.index)) splitSelection.delete(page.index);
        else splitSelection.add(page.index);
        $("#split-ranges").value = rangesFromSelection(splitSelection);
        cell.classList.toggle("picked", splitSelection.has(page.index));
      });

      // A magnifier so a page can still be inspected while Split is using
      // plain clicks for selection.
      if (isSplit) {
        const zoom = document.createElement("span");
        zoom.className = "pv-zoom";
        zoom.title = "View larger";
        zoom.textContent = "⤢";
        zoom.addEventListener("click", (e) => {
          e.stopPropagation();
          openLightbox(path, page.index);
        });
        cell.appendChild(zoom);
      }

      grid.appendChild(cell);
    });
  });
}

/* ------------------------------------------------------------ lightbox -- */

let lightboxAt = -1;

function openLightbox(path, index) {
  const doc = documents.get(path);
  if (!doc || !doc.pages[index] || !doc.pages[index].dataUrl) return;

  lightboxAt = index;
  const box = $("#lightbox");
  $("#lightbox-img").src = doc.pages[index].dataUrl;
  $("#lightbox-label").textContent = `Page ${index + 1} of ${doc.count}`;
  $("#lightbox-prev").disabled = index === 0;
  $("#lightbox-next").disabled = index === doc.count - 1;
  box.hidden = false;
  requestAnimationFrame(() => box.classList.add("show"));
}

function stepLightbox(delta) {
  if (!previewPath || lightboxAt < 0) return;
  openLightbox(previewPath, lightboxAt + delta);
}

function closeLightbox() {
  const box = $("#lightbox");
  box.classList.remove("show");
  lightboxAt = -1;
  setTimeout(() => {
    if (lightboxAt < 0) box.hidden = true;
  }, 200);
}

/* ==========================================================================
   Arrange: the editable page grid
   ========================================================================== */

let dragIndex = null;

function loadPages(path) {
  const grid = $("#org-grid");
  organize.source = path;
  organize.pages = [];

  grid.textContent = "";
  const status = document.createElement("div");
  status.className = "grid-status";
  status.textContent = "Reading document...";
  grid.appendChild(status);
  $(".org-toolbar").hidden = true;
  $('.run-btn[data-run="organize"]').hidden = true;

  pagesOf(path, function fill(doc) {
    if (organize.source !== path) return;
    if (doc.failed) {
      grid.textContent = "";
      showToast("error", "Arrange", "That PDF couldn't be opened. It may be encrypted or damaged.");
      return;
    }
    if (!doc.count) return;

    // Seeded once from the shared store, then owned here: reordering and
    // rotating are edits to this view, not to the rendered document.
    if (organize.pages.length !== doc.count) {
      organize.pages = doc.pages.map((p) => ({
        originalIndex: p.index,
        rotation: 0,
        selected: false,
      }));
    }
    renderPages(doc);
  });
}

function thumbnailFor(originalIndex) {
  const doc = documents.get(organize.source);
  const page = doc && doc.pages[originalIndex];
  return page ? page.dataUrl : null;
}

function renderPages() {
  const grid = $("#org-grid");
  grid.textContent = "";

  const hasPages = organize.pages.length > 0;
  $(".org-toolbar").hidden = !hasPages;
  $('.run-btn[data-run="organize"]').hidden = !hasPages;

  const selectedCount = organize.pages.filter((p) => p.selected).length;
  $(".org-count").textContent =
    plural(organize.pages.length, "page") +
    (selectedCount ? ` · ${selectedCount} selected` : " · drag to reorder, click to select");

  ["#org-move-l", "#org-move-r", "#org-rotate-l", "#org-rotate-r", "#org-delete"].forEach(
    (id) => {
      $(id).disabled = selectedCount === 0;
    }
  );

  if (!hasPages) {
    const empty = document.createElement("div");
    empty.className = "grid-status";
    empty.textContent = "Every page was deleted. Remove the file and add it again to start over.";
    grid.appendChild(empty);
    return;
  }

  organize.pages.forEach((page, i) => {
    const item = document.createElement("div");
    item.className = "thumb" + (page.selected ? " selected" : "");
    item.draggable = true;

    const dataUrl = thumbnailFor(page.originalIndex);
    if (dataUrl) {
      const img = document.createElement("img");
      img.src = dataUrl;
      img.alt = "";
      // Chromium treats dragging an <img> as "drag this picture out as a
      // file", which Qt then sees as a file drop and the app offers to add it
      // to the tray. The tile is what should be draggable, never the picture.
      img.draggable = false;
      img.style.transform = `rotate(${page.rotation}deg)`;
      item.appendChild(img);
    } else {
      const fail = document.createElement("div");
      fail.className = "thumb-fail";
      fail.textContent = "...";
      item.appendChild(fail);
    }

    const label = document.createElement("div");
    label.className = "thumb-label";
    label.textContent =
      `Page ${page.originalIndex + 1}` + (page.rotation ? ` · ${page.rotation}°` : "");
    item.appendChild(label);

    item.addEventListener("click", (e) => {
      if (!e.shiftKey && !e.ctrlKey && !e.metaKey) {
        organize.pages.forEach((p) => {
          if (p !== page) p.selected = false;
        });
      }
      page.selected = !page.selected;
      renderPages();
    });

    item.addEventListener("dragstart", (e) => {
      dragIndex = i;
      item.classList.add("dragging");
      // Firefox refuses to start a drag without payload, and Chromium wants
      // the effect set for the cursor to read as "move" rather than "copy".
      if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = "move";
        try {
          e.dataTransfer.setData("text/plain", String(i));
        } catch (err) {
          /* some engines lock dataTransfer during synthetic events */
        }
      }
    });

    item.addEventListener("dragend", () => {
      dragIndex = null;
      item.classList.remove("dragging");
      clearDropMarkers();
    });

    item.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (dragIndex === null) return;
      if (e.dataTransfer) e.dataTransfer.dropEffect = "move";

      // Which side of the page you are hovering decides whether it lands
      // before or after it. Highlighting the whole tile instead left you
      // guessing which way a page was about to jump.
      const box = item.getBoundingClientRect();
      const after = e.clientX > box.left + box.width / 2;
      clearDropMarkers();
      item.classList.add(after ? "drop-after" : "drop-before");
    });

    item.addEventListener("dragleave", () => {
      item.classList.remove("drop-before", "drop-after");
    });

    item.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const after = item.classList.contains("drop-after");
      clearDropMarkers();
      if (dragIndex === null) return;

      const box = item.getBoundingClientRect();
      const insertAfter = after || e.clientX > box.left + box.width / 2;
      movePage(dragIndex, insertAfter ? i + 1 : i);
      dragIndex = null;
    });

    grid.appendChild(item);
  });
}

function clearDropMarkers() {
  $$("#org-grid .thumb").forEach((el) => el.classList.remove("drop-before", "drop-after"));
}

/** Move the page at `from` so it sits at `to` in the new order. */
function movePage(from, to) {
  if (from === to || from + 1 === to) return;
  const [moved] = organize.pages.splice(from, 1);
  // Removing the page first shifts everything after it down by one.
  organize.pages.splice(to > from ? to - 1 : to, 0, moved);
  renderPages();
}

/** Shift every selected page one slot in `delta`, keeping their order. */
function nudgeSelected(delta) {
  const indices = organize.pages
    .map((p, i) => (p.selected ? i : -1))
    .filter((i) => i >= 0);
  if (!indices.length) return;

  // Walk from the edge the pages are moving towards, so a block of adjacent
  // selections slides as one instead of piling onto itself.
  const ordered = delta > 0 ? indices.slice().reverse() : indices;
  for (const i of ordered) {
    const target = i + delta;
    if (target < 0 || target >= organize.pages.length) return;
    if (organize.pages[target].selected) continue;
    const [moved] = organize.pages.splice(i, 1);
    organize.pages.splice(target, 0, moved);
  }
  renderPages();
}

function rotateSelected(delta) {
  organize.pages.forEach((p) => {
    if (p.selected) p.rotation = (((p.rotation + delta) % 360) + 360) % 360;
  });
  renderPages();
}

/* ==========================================================================
   Running things
   ========================================================================== */

function setBusy(featureId, busy, busyLabel) {
  const btn = $(`.run-btn[data-run="${featureId}"]`);
  if (!btn) return;
  if (busy) {
    btn.dataset.idleLabel = btn.dataset.idleLabel || btn.textContent;
    btn.textContent = busyLabel || "Working…";
  } else if (btn.dataset.idleLabel) {
    btn.textContent = btn.dataset.idleLabel;
  }
  btn.disabled = busy;
  btn.classList.toggle("busy", busy);
  btn.setAttribute("aria-busy", busy ? "true" : "false");
  btn.setAttribute("aria-disabled", busy ? "true" : "false");
  $("#detail").setAttribute("aria-busy", busy ? "true" : "false");
}

function onResult(featureId, finishedSignal, failedSignal, onSuccess) {
  finishedSignal.connect((json) => {
    setBusy(featureId, false);
    onSuccess(JSON.parse(json));
  });
  failedSignal.connect((message) => {
    setBusy(featureId, false);
    const feature = features.get(featureId);
    showToast("error", feature ? feature.title : "Pawdf", message);
  });
}

function wireRunButtons() {
  // No save dialogs and no folder pickers: every result goes to Downloads
  // under a name derived from the input. See Bridge._out_file in gui/bridge.py.
  $('.run-btn[data-run="split"]').addEventListener("click", () => {
    const [input] = filesFor("split");
    const ranges = $("#split-ranges")
      .value.split(",")
      .map((r) => r.trim())
      .filter(Boolean);
    if (!ranges.length) {
      return showToast("error", "Split", "Enter at least one page range, like 1-3.");
    }
    setBusy("split", true, "Splitting…");
    bridge.runSplit(input, JSON.stringify(ranges));
  });

  $('.run-btn[data-run="merge"]').addEventListener("click", () => {
    const files = filesFor("merge");
    if (files.length < 2) return showToast("error", "Merge", "Add at least two PDFs.");
    setBusy("merge", true, "Merging…");
    bridge.runMerge(JSON.stringify(files));
  });

  $('.run-btn[data-run="organize"]').addEventListener("click", () => {
    if (!organize.source || !organize.pages.length) {
      return showToast("error", "Arrange", "Nothing to save.");
    }
    const edits = organize.pages.map((p) => [p.originalIndex, p.rotation]);
    setBusy("organize", true, "Saving…");
    bridge.runOrganize(organize.source, JSON.stringify(edits));
  });

  $('.run-btn[data-run="compress"]').addEventListener("click", () => {
    setBusy("compress", true, "Compressing…");
    bridge.runCompress(filesFor("compress")[0], $("#compress-preset").value);
  });

  $('.run-btn[data-run="rasterize"]').addEventListener("click", () => {
    setBusy("rasterize", true, "Rendering…");
    bridge.runRasterize(
      filesFor("rasterize")[0],
      $("#raster-format").value,
      Number($("#raster-dpi").value)
    );
  });

  $('.run-btn[data-run="imagepdf"]').addEventListener("click", () => {
    setBusy("imagepdf", true, "Building…");
    bridge.runImagePdf(JSON.stringify(filesFor("imagepdf")), $("#imagepdf-fit").value);
  });

  $('.run-btn[data-run="rotate"]').addEventListener("click", () => {
    setBusy("rotate", true, "Rotating...");
    bridge.runRotate(
      filesFor("rotate")[0],
      JSON.stringify({
        degrees: Number($("#rotate-degrees").value),
        pages: $("#rotate-pages").value.trim(),
      }),
      $("#rotate-absolute").checked
    );
  });

  $('.run-btn[data-run="crop"]').addEventListener("click", () => {
    const edges = ["top", "bottom", "left", "right"];
    const values = {};
    for (const edge of edges) {
      const raw = Number($(`#crop-${edge}`).value);
      if (!Number.isFinite(raw) || raw < 0) {
        return showToast("error", "Crop", `${edge} must be zero or more.`);
      }
      values[edge] = raw;
    }
    if (edges.every((e) => values[e] === 0)) {
      return showToast("error", "Crop", "Set at least one edge to trim.");
    }
    values.pages = $("#crop-pages").value.trim();

    setBusy("crop", true, "Cropping...");
    bridge.runCrop(filesFor("crop")[0], JSON.stringify(values));
  });

  $('.run-btn[data-run="repair"]').addEventListener("click", () => {
    setBusy("repair", true, "Repairing...");
    bridge.runRepair(filesFor("repair")[0]);
  });

  $('.run-btn[data-run="protect"]').addEventListener("click", () => {
    const password = $("#protect-password").value;
    if (!password) return showToast("error", "Protect", "Choose a password first.");

    setBusy("protect", true, "Protecting...");
    bridge.runProtect(
      filesFor("protect")[0],
      JSON.stringify({
        password,
        allowPrint: $("#protect-print").checked,
        allowModify: $("#protect-modify").checked,
        allowExtract: $("#protect-extract").checked,
      })
    );
  });

  $('.run-btn[data-run="unlock"]').addEventListener("click", () => {
    setBusy("unlock", true, "Unlocking...");
    bridge.runUnlock(filesFor("unlock")[0], $("#unlock-password").value);
  });

  $('.run-btn[data-run="watermark"]').addEventListener("click", () => {
    const text = $("#wm-text").value.trim();
    if (!text) return showToast("error", "Watermark", "Type the text to stamp.");

    setBusy("watermark", true, "Stamping...");
    bridge.runWatermark(
      filesFor("watermark")[0],
      JSON.stringify({
        text,
        position: $("#wm-position").value,
        rotation: Number($("#wm-rotation").value),
        opacity: Number($("#wm-opacity").value),
        fontSize: Number($("#wm-size").value),
      })
    );
  });

  $("#sign-image-zone").addEventListener("click", () => {
    bridge.pickOpenFile("Choose a signature image", "image", (path) => {
      if (!path) return;
      signatureImage = path;
      $("#sign-image-name").textContent = baseName(path);
      $("#sign-image-zone").classList.add("loaded");
    });
  });

  $('.run-btn[data-run="sign"]').addEventListener("click", () => {
    if (!signatureImage) return showToast("error", "Sign", "Choose a signature image first.");

    setBusy("sign", true, "Stamping...");
    bridge.runSign(
      filesFor("sign")[0],
      signatureImage,
      JSON.stringify({
        position: $("#sign-position").value,
        width: Number($("#sign-width").value),
        pages: $("#sign-pages").value.trim(),
      })
    );
  });

  $('.run-btn[data-run="pagenumbers"]').addEventListener("click", () => {
    const startAt = Number($("#pn-start").value);
    if (!Number.isFinite(startAt)) {
      return showToast("error", "Page numbers", "Start must be a number.");
    }

    setBusy("pagenumbers", true, "Numbering...");
    bridge.runPageNumbers(
      filesFor("pagenumbers")[0],
      JSON.stringify({
        position: $("#pn-position").value,
        startAt,
        template: $("#pn-template").value,
        skipFirst: $("#pn-skip-first").checked,
      })
    );
  });

  $('.run-btn[data-run="forms"]').addEventListener("click", () => {
    const values = {};
    for (const input of $$("#form-fields [data-field]")) {
      values[input.dataset.field] =
        input.type === "checkbox" ? (input.checked ? "yes" : "") : input.value;
    }
    if (!Object.keys(values).length) {
      return showToast("error", "Fill form", "This PDF has no supported editable fields.");
    }
    setBusy("forms", true, "Filling...");
    bridge.runFillForm(
      filesFor("forms")[0],
      JSON.stringify(values),
      $("#form-flatten").checked
    );
  });

  $('.run-btn[data-run="annotate"]').addEventListener("click", () => {
    const text = $("#ann-text").value.trim();
    if (!text) return showToast("error", "Annotate", "Type the note first.");

    const page = Number($("#ann-page").value);
    if (!Number.isFinite(page) || page < 1) {
      return showToast("error", "Annotate", "Page must be 1 or more.");
    }

    setBusy("annotate", true, "Drawing...");
    bridge.runAnnotate(
      filesFor("annotate")[0],
      JSON.stringify({
        text,
        page,
        x: Number($("#ann-x").value) || 72,
        y: Number($("#ann-y").value) || 720,
        size: Number($("#ann-size").value),
      })
    );
  });

  $('.run-btn[data-run="ocr"]').addEventListener("click", () => {
    setBusy("ocr", true, "Reading pages...");
    bridge.runOcr(
      filesFor("ocr")[0],
      $("#ocr-language").value,
      Number($("#ocr-dpi").value)
    );
  });

  $('.run-btn[data-run="pdf_to_markdown"]').addEventListener("click", () => {
    setBusy("pdf_to_markdown", true, "Converting...");
    bridge.runMarkdown(filesFor("pdf_to_markdown")[0], $("#md-separators").checked);
  });

  $('.run-btn[data-run="pdf_to_docx"]').addEventListener("click", () => {
    setBusy("pdf_to_docx", true, "Converting…");
    bridge.runPdfToWord(filesFor("pdf_to_docx")[0]);
  });

  $('.run-btn[data-run="xlsx_to_pdf"]').addEventListener("click", () => {
    setBusy("xlsx_to_pdf", true, "Converting...");
    bridge.runXlsxToPdf(filesFor("xlsx_to_pdf")[0]);
  });

  $('.run-btn[data-run="pptx_to_pdf"]').addEventListener("click", () => {
    setBusy("pptx_to_pdf", true, "Converting...");
    bridge.runPptxToPdf(filesFor("pptx_to_pdf")[0]);
  });

  $('.run-btn[data-run="docx_to_pdf"]').addEventListener("click", () => {
    setBusy("docx_to_pdf", true, "Converting…");
    bridge.runWordToPdf(filesFor("docx_to_pdf")[0]);
  });
}

function updateJobStatus(count) {
  const total = Number(count) || 0;
  const status = $("#job-status");
  if (status) {
    status.textContent = total
      ? `${plural(total, "job")} still writing. Pawdf will finish them before closing.`
      : "No background work is active.";
  }
  document.body.classList.toggle("processing", total > 0);
}

function refreshDiagnostics() {
  bridge.diagnosticInfo((json) => {
    const data = JSON.parse(json);
    const status = $("#diagnostics-status");
    if (!status) return;
    status.textContent =
      `Pawdf ${data.pawdfVersion} · ${data.system} ${data.release} · ` +
      `Python ${data.pythonVersion}`;
  });
  bridge.activeJobs((count) => updateJobStatus(count));
}

function wireSignals() {

  bridge.jobCountChanged.connect((count) => updateJobStatus(count));
  onResult("split", bridge.splitFinished, bridge.splitFailed, (d) =>
    showToast("success", "Split", `Wrote ${plural(d.count, "file")} to ${baseName(d.where)}.`, reveal(d.where))
  );
  onResult("merge", bridge.mergeFinished, bridge.mergeFailed, (d) =>
    showToast("success", "Merge", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("organize", bridge.organizeFinished, bridge.organizeFailed, (d) =>
    showToast("success", "Arrange", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("rasterize", bridge.rasterizeFinished, bridge.rasterizeFailed, (d) =>
    showToast("success", "PDF to Images", `Wrote ${plural(d.count, "image")} to ${baseName(d.where)}.`, reveal(d.where))
  );
  onResult("imagepdf", bridge.imagepdfFinished, bridge.imagepdfFailed, (d) =>
    showToast("success", "Images to PDF", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("pdf_to_docx", bridge.pdfToWordFinished, bridge.pdfToWordFailed, (d) =>
    showToast("success", "PDF to Word", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("docx_to_pdf", bridge.wordToPdfFinished, bridge.wordToPdfFailed, (d) =>
    showToast("success", "Word to PDF", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("compress", bridge.compressFinished, bridge.compressFailed, (d) => {
    const engine = d.method === "ghostscript" ? "Ghostscript" : "the built-in compressor";
    const pct = percentSaved(d.originalSize, d.compressedSize);
    const change =
      pct === null ? "" : pct > 0 ? `, ${pct}% smaller` : pct < 0 ? `, ${-pct}% larger` : ", no change";
    showToast(
      "success",
      "Compress",
      `Using ${engine}: ${humanSize(d.originalSize)} → ${humanSize(d.compressedSize)}${change}.`,
      reveal(d.output)
    );
  });

  onResult("rotate", bridge.rotateFinished, bridge.rotateFailed, (d) =>
    showToast("success", "Rotate", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("crop", bridge.cropFinished, bridge.cropFailed, (d) =>
    showToast("success", "Crop", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("protect", bridge.protectFinished, bridge.protectFailed, (d) => {
    $("#protect-password").value = "";
    showToast("success", "Protect", `Saved ${baseName(d.output)}. It now needs the password to open.`, reveal(d.output));
  });
  onResult("unlock", bridge.unlockFinished, bridge.unlockFailed, (d) => {
    $("#unlock-password").value = "";
    showToast("success", "Unlock", `Saved ${baseName(d.output)}, with no password.`, reveal(d.output));
  });
  onResult("repair", bridge.repairFinished, bridge.repairFailed, (d) => {
    // Say which of the three things happened, because "done" would hide the
    // two that matter: it was never broken, or it is still not clean.
    let message;
    if (d.wasAlreadyReadable) {
      message = `That file was not damaged. Rewrote it anyway: ${plural(d.pages, "page")}.`;
    } else if (d.isNowClean) {
      message = `Recovered ${plural(d.pages, "page")}. The result opens cleanly.`;
    } else {
      message = `Recovered ${plural(d.pages, "page")}, but the result still has structural problems.`;
    }
    showToast(d.isNowClean ? "success" : "error", "Repair", message, reveal(d.output));
  });

  onResult("watermark", bridge.watermarkFinished, bridge.watermarkFailed, (d) =>
    showToast("success", "Watermark", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("sign", bridge.signFinished, bridge.signFailed, (d) =>
    showToast("success", "Sign", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("pagenumbers", bridge.pagenumbersFinished, bridge.pagenumbersFailed, (d) =>
    showToast("success", "Page numbers", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );

  onResult("pdf_to_markdown", bridge.markdownFinished, bridge.markdownFailed, (d) =>
    showToast("success", "PDF to Markdown", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );

  onResult("xlsx_to_pdf", bridge.xlsxToPdfFinished, bridge.xlsxToPdfFailed, (d) =>
    showToast("success", "Excel to PDF", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("pptx_to_pdf", bridge.pptxToPdfFinished, bridge.pptxToPdfFailed, (d) => {
    const skipped = Number(d.shapesSkipped || 0);
    const warningCount = Number(
      d.warningCount || (Array.isArray(d.warnings) ? d.warnings.length : 0)
    );
    const affected = Math.max(skipped, warningCount);
    const warning =
      affected
        ? ` ${plural(affected, "shape")} had fidelity limitations. Review the output.`
        : "";
    showToast(
      skipped || warningCount ? "error" : "success",
      "PowerPoint to PDF",
      `Saved ${baseName(d.output)}.${warning}`,
      reveal(d.output)
    );
  });

  onResult("ocr", bridge.ocrFinished, bridge.ocrFailed, (d) => {
    const failedCount = d.failed.length;
    const note = failedCount
      ? ` ${plural(failedCount, "page")} ${failedCount === 1 ? "was" : "were"} retained unchanged because OCR failed.`
      : "";
    showToast(
      "success",
      "OCR",
      `${plural(d.pages, "page")} are now searchable.${note}`,
      reveal(d.output)
    );
  });

  onResult("forms", bridge.formsFinished, bridge.formsFailed, (d) =>
    showToast("success", "Fill form", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );
  onResult("annotate", bridge.annotateFinished, bridge.annotateFailed, (d) =>
    showToast("success", "Annotate", `Saved ${baseName(d.output)}.`, reveal(d.output))
  );

  bridge.thumbnailReady.connect((json) => onThumbnail(JSON.parse(json)));

  bridge.ghostscriptFinished.connect((json) => {
    const data = JSON.parse(json);
    refreshGhostscript();
    showToast("success", "Ghostscript", data.instructions || `Ready at ${data.path}`);
  });
  bridge.ghostscriptFailed.connect((message) => {
    refreshGhostscript();
    showToast("error", "Ghostscript", message);
  });

  // Native drag-and-drop. The page cannot read a dropped file's path itself;
  // see gui/dnd.py for why these arrive from Python instead.
  bridge.dragStateChanged.connect((active) =>
    document.body.classList.toggle("dragging", active)
  );
  bridge.filesDropped.connect((json) => {
    document.body.classList.remove("dragging");
    addFiles(JSON.parse(json));
  });
}

function refreshTesseract() {
  bridge.tesseractStatus((json) => {
    const data = JSON.parse(json);
    const note = $("#ocr-note");
    const status = $("#ocr-status");
    const runBtn = $('.run-btn[data-run="ocr"]');
    const languages = $("#ocr-language");

    if (data.found) {
      note.textContent =
        "Recognised text is placed invisibly behind the original image, so the " +
        "page still looks exactly like the scan and can now be searched.";
      status.textContent = `Installed.\n${data.path}`;
      runBtn.disabled = false;

      if (data.languages.length) {
        const chosen = languages.value;
        languages.textContent = "";
        for (const code of data.languages) {
          const option = document.createElement("option");
          option.value = code;
          option.textContent = code;
          languages.appendChild(option);
        }
        languages.value = data.languages.includes(chosen) ? chosen : data.languages[0];
      }
    } else {
      // The instructions carry the exact command for this platform, so show
      // them rather than a bare "not found".
      note.textContent = data.instructions;
      status.textContent = data.instructions;
      runBtn.disabled = true;
    }
  });
}

function refreshGhostscript() {
  bridge.ghostscriptStatus((json) => {
    const data = JSON.parse(json);
    const status = $("#gs-status");
    const action = $("#gs-action");
    const note = $("#gs-note");

    if (data.found) {
      status.textContent = `Installed.\n${data.path}`;
      action.textContent = "Check again";
      note.textContent = "Ghostscript is installed, so these presets apply directly.";
    } else {
      status.textContent =
        "Not installed. Compress still works using the built-in compressor, which is less aggressive.";
      action.textContent = "Set up Ghostscript";
      note.textContent =
        "Ghostscript isn't installed, so the built-in compressor will be used and the preset has less effect.";
    }
  });
}

/* ------------------------------------------------------------ chrome -- */

function promptForFiles() {
  bridge.pickOpenFiles("Add files", "any", (paths) => {
    if (paths && paths.length) addFiles(paths);
  });
}

function wireSplitPreviewSync() {
  const field = $("#split-ranges");
  field.addEventListener("input", () => {
    if (session.tool !== "split" || !previewPath) return;
    const doc = documents.get(previewPath);
    if (!doc || !doc.count) return;
    splitSelection.clear();
    selectionFromRanges(field.value, doc.count).forEach((i) => splitSelection.add(i));
    $$("#preview-grid .pv-page").forEach((cell, i) =>
      cell.classList.toggle("picked", splitSelection.has(i))
    );
  });
}

function wireLightbox() {
  $("#lightbox-close").addEventListener("click", closeLightbox);
  $("#lightbox-prev").addEventListener("click", () => stepLightbox(-1));
  $("#lightbox-next").addEventListener("click", () => stepLightbox(1));
  $("#lightbox").addEventListener("click", (e) => {
    if (e.target.id === "lightbox") closeLightbox();
  });
}

function wireSearch() {
  $("#search-input").addEventListener("input", (e) => renderSearch(e.target.value));
  $("#search-close").addEventListener("click", closeSearch);
  $("#search").addEventListener("click", (e) => {
    if (e.target.id === "search") closeSearch();
  });
  $("#search-input").addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      moveSearch(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      moveSearch(-1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      commitSearch();
    } else if (e.key === "Escape") {
      closeSearch();
    }
  });
}

function wireChrome() {
  $("#hub").addEventListener("click", hubPressed);
  $("#tray-add").addEventListener("click", promptForFiles);
  $("#hero-add").addEventListener("click", promptForFiles);
  $("#hero-search").addEventListener("click", openSearch);
  $("#tray-clear").addEventListener("click", clearFiles);
  $("#detail-back").addEventListener("click", closeTool);
  $("#theme-toggle").addEventListener("click", toggleTheme);
  $("#gs-theme").addEventListener("click", toggleTheme);
  $("#open-settings").addEventListener("click", () => openTool("settings"));
  $("#gs-action").addEventListener("click", () => bridge.setupGhostscript());

  $("#diagnostics-export").addEventListener("click", () => {
    bridge.exportDiagnostics((path) => {
      if (!path) return;
      showToast(
        "success",
        "Diagnostics",
        `Saved ${baseName(path)}. Review it before sharing.`,
        reveal(path)
      );
      refreshDiagnostics();
    });
  });
  $("#diagnostics-clear").addEventListener("click", () => {
    bridge.clearDiagnosticLogs();
    showToast("success", "Diagnostics", "Local Pawdf logs were cleared.");
    refreshDiagnostics();
  });
  $("#session-forget").addEventListener("click", forgetRememberedSession);

  $("#org-move-l").addEventListener("click", () => nudgeSelected(-1));
  $("#org-move-r").addEventListener("click", () => nudgeSelected(1));
  $("#org-rotate-l").addEventListener("click", () => rotateSelected(-90));
  $("#org-rotate-r").addEventListener("click", () => rotateSelected(90));
  $("#org-delete").addEventListener("click", () => {
    organize.pages = organize.pages.filter((p) => !p.selected);
    renderPages();
  });

  document.addEventListener("keydown", (e) => {
    const searchOpen = !$("#search").hidden;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (searchOpen) closeSearch();
      else openSearch();
      return;
    }
    if (searchOpen) return; // the overlay handles its own keys

    if (e.target instanceof HTMLInputElement) return;

    if (lightboxAt >= 0) {
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowLeft") stepLightbox(-1);
      if (e.key === "ArrowRight") stepLightbox(1);
      return;
    }
    if (e.key === "Escape") {
      // One level at a time: tool, then category, then nothing.
      if (session.tool) closeTool();
      else if (session.category) leaveCategory();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "o") {
      e.preventDefault();
      promptForFiles();
      return;
    }
    // Number keys pick from whatever the ring is currently showing.
    const digit = Number(e.key);
    if (digit >= 1 && digit <= 9) {
      if (session.category === null) {
        const list = Array.from(categories.values());
        if (list[digit - 1]) openCategory(list[digit - 1].id);
      } else {
        const list = featuresIn(session.category);
        if (list[digit - 1]) openTool(list[digit - 1].id);
      }
    }
  });

  // Chromium treats a dropped file as a navigation, which would replace the
  // whole UI with the PDF. The native handler does the real work; these two
  // just stop the default behaviour.
  ["dragover", "drop"].forEach((type) =>
    document.addEventListener(type, (e) => e.preventDefault())
  );
}

/* --------------------------------------------------------------- boot -- */

function boot() {
  try {
    // Light is the default; the markup already says so. Only a deliberate
    // switch is remembered.
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") applyTheme(saved);
  } catch (err) {
    /* storage unavailable; the default theme stands */
  }

  bridge.features((json) => {
    const payload = JSON.parse(json);
    payload.categories.forEach((c) => categories.set(c.id, c));
    payload.features.forEach((f) => features.set(f.id, f));
    renderRing();

    wireRunButtons();
    wireSignals();
    wireChrome();
    wireSplitPreviewSync();
    wireLightbox();
    wireSearch();
    renderFiles();
    restoreSession();
    refreshGhostscript();
    refreshTesseract();
  });

  bridge.appInfo((json) => {
    $("#app-version").textContent = "v" + JSON.parse(json).version;
  });
}

new QWebChannel(qt.webChannelTransport, (channel) => {
  bridge = channel.objects.bridge;
  boot();
});
