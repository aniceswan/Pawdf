/* Pawdf UX upgrade: stable ring, scissors split, pointer Arrange, and result pipelines. */
"use strict";

const pawdfOriginalShowPreview = showPreview;
const pawdfOriginalWireRunButtons = wireRunButtons;
const pawdfOriginalWireSignals = wireSignals;
const pawdfOriginalSetBusy = setBusy;
const pawdfOriginalOpenTool = openTool;

const splitUx = {
  path: null,
  count: 0,
  cuts: new Set(),
  selected: new Set(),
};

let resultPaths = [];
let resultFeatureId = null;
let arrangePointer = null;
let suppressArrangeClick = false;

function installUxContainers() {
  const splitPanel = $('.panel[data-panel="split"]');
  const legacyRanges = $("#split-ranges");
  if (splitPanel && legacyRanges && !$("#split-plan")) {
    const legacyField = legacyRanges.closest("label");
    if (legacyField) legacyField.hidden = true;

    const intro = document.createElement("div");
    intro.className = "split-intro";
    intro.innerHTML =
      '<div><strong>Choose the cut points</strong><span>Press a scissors button between two pages. One cut creates two files.</span></div>' +
      '<button type="button" class="ghost-btn" id="split-clear-cuts">Clear cuts</button>';

    const plan = document.createElement("section");
    plan.id = "split-plan";
    plan.className = "split-plan";
    plan.innerHTML =
      '<header class="split-plan-head"><div><strong>Output files</strong><span id="split-summary">Add a cut to begin.</span></div>' +
      '<button type="button" class="link-btn" id="split-select-all">Select all</button></header>' +
      '<div id="split-plan-list" class="split-plan-list"></div>';

    splitPanel.insertBefore(intro, splitPanel.firstChild);
    splitPanel.insertBefore(plan, $('.run-btn[data-run="split"]'));

    $("#split-clear-cuts").addEventListener("click", () => {
      splitUx.cuts.clear();
      resetSplitSelection();
      refreshSplitCutButtons();
      renderSplitPlan();
    });
    $("#split-select-all").addEventListener("click", () => {
      splitUx.selected = new Set(splitSegments().map(segmentKey));
      renderSplitPlan();
    });
  }

  const detailBody = $(".detail-body");
  if (detailBody && !$("#operation-results")) {
    const section = document.createElement("section");
    section.id = "operation-results";
    section.className = "operation-results";
    section.hidden = true;
    section.innerHTML =
      '<header class="results-head"><div><span class="results-eyebrow">Results</span><h2 id="results-title"></h2></div>' +
      '<button type="button" class="ghost-btn" id="results-save-all">Save all</button></header>' +
      '<div id="results-list" class="results-list"></div>';
    detailBody.appendChild(section);
    $("#results-save-all").addEventListener("click", saveAllResults);
  }
}

installUxContainers();

function segmentKey(segment) {
  return `${segment.start}-${segment.end}`;
}

function splitSegments() {
  if (!splitUx.count) return [];
  const cuts = [...splitUx.cuts]
    .filter((cut) => cut >= 1 && cut < splitUx.count)
    .sort((a, b) => a - b);
  const segments = [];
  let start = 1;
  for (const cut of cuts) {
    segments.push({ start, end: cut });
    start = cut + 1;
  }
  segments.push({ start, end: splitUx.count });
  return segments;
}

function splitRangeText(segment) {
  return segment.start === segment.end
    ? String(segment.start)
    : `${segment.start}-${segment.end}`;
}

function resetSplitSelection() {
  splitUx.selected = new Set(splitSegments().map(segmentKey));
}

function refreshSplitCutButtons() {
  $$("#preview-grid .split-cutter").forEach((button) => {
    const cut = Number(button.dataset.cut);
    const active = splitUx.cuts.has(cut);
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
    button.title = active ? `Remove cut after page ${cut}` : `Cut after page ${cut}`;
  });
}

function renderSplitPlan() {
  const list = $("#split-plan-list");
  const summary = $("#split-summary");
  const selectAll = $("#split-select-all");
  const runButton = $('.run-btn[data-run="split"]');
  if (!list || !summary || !runButton) return;

  const segments = splitSegments();
  const validKeys = new Set(segments.map(segmentKey));
  splitUx.selected = new Set([...splitUx.selected].filter((key) => validKeys.has(key)));

  list.textContent = "";
  segments.forEach((segment, index) => {
    const key = segmentKey(segment);
    const row = document.createElement("label");
    row.className = "split-output";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = splitUx.selected.has(key);
    checkbox.disabled = splitUx.cuts.size === 0;
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) splitUx.selected.add(key);
      else splitUx.selected.delete(key);
      renderSplitPlan();
    });

    const text = document.createElement("span");
    text.className = "split-output-text";
    const pages = segment.start === segment.end
      ? `Page ${segment.start}`
      : `Pages ${segment.start}–${segment.end}`;
    text.innerHTML = `<strong>Part ${index + 1}</strong><span>${pages}</span>`;

    const badge = document.createElement("span");
    badge.className = "split-output-badge";
    badge.textContent = `${segment.end - segment.start + 1}p`;

    row.append(checkbox, text, badge);
    list.appendChild(row);
  });

  const selectedCount = splitUx.selected.size;
  const hasCuts = splitUx.cuts.size > 0;
  summary.textContent = hasCuts
    ? `${segments.length} parts · ${selectedCount} selected`
    : "Press scissors between pages to create multiple files.";
  selectAll.hidden = !hasCuts || selectedCount === segments.length;
  runButton.disabled = !hasCuts || selectedCount === 0;
  runButton.textContent = selectedCount > 1 ? `Create ${selectedCount} files` : "Create selected file";

  const legacyRanges = $("#split-ranges");
  if (legacyRanges) {
    legacyRanges.value = segments
      .filter((segment) => splitUx.selected.has(segmentKey(segment)))
      .map(splitRangeText)
      .join(", ");
  }
}

function buildSplitPreview(doc) {
  const grid = $("#preview-grid");
  if (!grid) return;
  grid.classList.add("split-mode");

  const needsBuild = grid.dataset.splitPath !== splitUx.path ||
    Number(grid.dataset.splitCount || 0) !== doc.count;
  if (needsBuild) {
    grid.textContent = "";
    grid.dataset.splitPath = splitUx.path;
    grid.dataset.splitCount = String(doc.count);

    doc.pages.forEach((page) => {
      const unit = document.createElement("div");
      unit.className = "split-page-unit";
      unit.dataset.page = String(page.index);

      const card = document.createElement("button");
      card.type = "button";
      card.className = "pv-page split-page-card";
      card.title = `View page ${page.index + 1}`;

      const media = document.createElement("span");
      media.className = "split-page-media";
      const placeholder = document.createElement("span");
      placeholder.className = "pv-placeholder";
      media.appendChild(placeholder);

      const number = document.createElement("span");
      number.className = "pv-num";
      number.textContent = String(page.index + 1);
      card.append(media, number);
      card.addEventListener("click", () => openLightbox(splitUx.path, page.index));
      unit.appendChild(card);

      if (page.index < doc.count - 1) {
        const cutter = document.createElement("button");
        cutter.type = "button";
        cutter.className = "split-cutter";
        cutter.dataset.cut = String(page.index + 1);
        cutter.setAttribute("aria-label", `Cut after page ${page.index + 1}`);
        cutter.setAttribute("aria-pressed", "false");
        cutter.innerHTML = '<span aria-hidden="true">✂</span>';
        cutter.addEventListener("click", () => {
          const cut = page.index + 1;
          if (splitUx.cuts.has(cut)) splitUx.cuts.delete(cut);
          else splitUx.cuts.add(cut);
          resetSplitSelection();
          refreshSplitCutButtons();
          renderSplitPlan();
        });
        unit.appendChild(cutter);
      }
      grid.appendChild(unit);
    });
  }

  doc.pages.forEach((page) => {
    const unit = $(`.split-page-unit[data-page="${page.index}"]`, grid);
    if (!unit) return;
    const media = $(".split-page-media", unit);
    if (!media) return;
    if (page.dataUrl) {
      let image = $("img", media);
      if (!image) {
        image = document.createElement("img");
        image.alt = "";
        media.textContent = "";
        media.appendChild(image);
      }
      if (image.src !== page.dataUrl) image.src = page.dataUrl;
    } else {
      const placeholder = $(".pv-placeholder", media);
      if (placeholder) placeholder.textContent = page.settled ? "!" : "";
    }
  });

  refreshSplitCutButtons();
  renderSplitPlan();
}

function renderSplitDocument(doc) {
  const path = splitUx.path;
  const grid = $("#preview-grid");
  if (!path || !grid || previewPath !== path) return;

  if (doc.failed) {
    grid.textContent = "";
    const status = document.createElement("div");
    status.className = "grid-status";
    status.textContent = "That PDF couldn't be opened.";
    grid.appendChild(status);
    return;
  }
  if (!doc.count) return;

  splitUx.count = doc.count;
  $("#preview-count").textContent = plural(doc.count, "page");
  if (!splitUx.selected.size) resetSplitSelection();
  buildSplitPreview(doc);
}

showPreview = function enhancedShowPreview(featureId, path) {
  const grid = $("#preview-grid");
  if (featureId !== "split") {
    if (grid) {
      grid.classList.remove("split-mode");
      delete grid.dataset.splitPath;
      delete grid.dataset.splitCount;
    }
    return pawdfOriginalShowPreview(featureId, path);
  }

  const wrap = $("#preview");
  if (!path) {
    wrap.hidden = true;
    previewPath = null;
    return;
  }

  wrap.hidden = false;
  previewPath = path;
  $("#preview-hint").textContent = "Press scissors between pages. Click a page to inspect it.";

  if (splitUx.path !== path) {
    splitUx.path = path;
    splitUx.count = 0;
    splitUx.cuts.clear();
    splitUx.selected.clear();
    if (grid) {
      grid.textContent = "";
      delete grid.dataset.splitPath;
      delete grid.dataset.splitCount;
    }
  }

  if (grid && !grid.children.length) {
    const status = document.createElement("div");
    status.className = "grid-status";
    status.textContent = "Reading document...";
    grid.appendChild(status);
  }

  pagesOf(path, renderSplitDocument);
};

wireSplitPreviewSync = function disableLegacySplitSelection() {};

function clearOperationResults() {
  resultPaths = [];
  resultFeatureId = null;
  const section = $("#operation-results");
  if (section) section.hidden = true;
  const list = $("#results-list");
  if (list) list.textContent = "";
}

setBusy = function enhancedSetBusy(featureId, busy, busyLabel) {
  if (busy) clearOperationResults();
  pawdfOriginalSetBusy(featureId, busy, busyLabel);
};

openTool = function enhancedOpenTool(featureId) {
  if (session.tool && session.tool !== featureId) clearOperationResults();
  pawdfOriginalOpenTool(featureId);
};

function compatibleTools(path, sourceFeatureId) {
  const ext = extensionOf(path);
  return Array.from(features.values()).filter(
    (feature) => feature.id !== sourceFeatureId && feature.accepts.includes(ext)
  );
}

function continueWith(path, featureId) {
  const feature = features.get(featureId);
  if (!feature) return;
  session.files = [path];
  organize.source = null;
  organize.pages = [];
  renderFiles();
  session.category = feature.category;
  clearOperationResults();
  renderRing();
  openTool(featureId);
}

function makeContinueMenu(path, sourceFeatureId) {
  const menu = document.createElement("div");
  menu.className = "continue-menu";
  const tools = compatibleTools(path, sourceFeatureId);

  if (!tools.length) {
    const empty = document.createElement("span");
    empty.className = "continue-empty";
    empty.textContent = `No Pawdf tool accepts ${extensionOf(path) || "this file type"}.`;
    menu.appendChild(empty);
    return menu;
  }

  tools.forEach((feature) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "continue-tool";
    button.style.setProperty("--node-hue", String(feature.hue));
    button.innerHTML =
      `<svg viewBox="0 0 24 24">${ICONS[feature.id] || ""}</svg>` +
      `<span><strong></strong><small></small></span>`;
    $("strong", button).textContent = feature.title;
    $("small", button).textContent = feature.tagline;
    button.addEventListener("click", () => continueWith(path, feature.id));
    menu.appendChild(button);
  });
  return menu;
}

function saveOneResult(path, button) {
  if (!bridge.saveOutput) {
    bridge.revealPath(path);
    showToast("success", "Result", "The output is already saved. Opened its folder.");
    return;
  }
  button.disabled = true;
  bridge.saveOutput(path, (saved) => {
    button.disabled = false;
    if (saved) showToast("success", "Saved", `Saved ${baseName(saved)}.`, reveal(saved));
  });
}

function saveAllResults() {
  if (!resultPaths.length) return;
  const button = $("#results-save-all");
  if (!bridge.saveOutputs) {
    bridge.revealPath(resultPaths[0]);
    showToast("success", "Results", "The outputs are already saved. Opened their folder.");
    return;
  }
  button.disabled = true;
  bridge.saveOutputs(JSON.stringify(resultPaths), (json) => {
    button.disabled = false;
    let saved = [];
    try {
      saved = JSON.parse(json || "[]");
    } catch (error) {
      showToast("error", "Save", "Pawdf could not read the save result.");
      return;
    }
    if (saved.length) {
      showToast("success", "Saved", `Saved ${plural(saved.length, "file")}.`, reveal(saved[0]));
    }
  });
}

function showOperationResults(featureId, data) {
  const paths = Array.isArray(data.outputs)
    ? data.outputs
    : data.output
      ? [data.output]
      : [];
  resultPaths = [...new Set(paths.filter(Boolean))];
  resultFeatureId = featureId;
  if (!resultPaths.length) return;

  const section = $("#operation-results");
  const list = $("#results-list");
  const title = $("#results-title");
  const saveAll = $("#results-save-all");
  if (!section || !list || !title || !saveAll) return;

  const feature = features.get(featureId);
  title.textContent = `${feature ? feature.title : "Operation"} complete`;
  saveAll.hidden = resultPaths.length < 2;
  list.textContent = "";

  resultPaths.forEach((path, index) => {
    const card = document.createElement("article");
    card.className = "result-card";

    const icon = document.createElement("div");
    icon.className = "result-kind";
    icon.textContent = (extensionOf(path) || "file").replace(".", "").toUpperCase();

    const info = document.createElement("div");
    info.className = "result-info";
    const name = document.createElement("strong");
    name.textContent = baseName(path);
    name.title = path;
    const meta = document.createElement("span");
    meta.textContent = resultPaths.length > 1 ? `Output ${index + 1} of ${resultPaths.length}` : "Ready";
    info.append(name, meta);

    const actions = document.createElement("div");
    actions.className = "result-actions";
    const save = document.createElement("button");
    save.type = "button";
    save.className = "result-save";
    save.textContent = "Save";
    save.addEventListener("click", () => saveOneResult(path, save));

    const next = document.createElement("button");
    next.type = "button";
    next.className = "result-continue";
    next.textContent = "Continue";
    const tools = compatibleTools(path, featureId);
    next.disabled = tools.length === 0;
    next.title = tools.length ? "Send this output to another tool" : "No compatible next tool";

    const menu = makeContinueMenu(path, featureId);
    menu.id = `continue-menu-${index}`;
    menu.hidden = true;
    menu.setAttribute("role", "menu");
    next.setAttribute("aria-haspopup", "menu");
    next.setAttribute("aria-controls", menu.id);
    next.setAttribute("aria-expanded", "false");
    next.addEventListener("click", (event) => {
      event.stopPropagation();
      const opening = menu.hidden;
      closeContinueMenus(menu);
      menu.hidden = !opening;
      next.setAttribute("aria-expanded", String(opening));
    });
    menu.addEventListener("click", (event) => event.stopPropagation());

    actions.append(save, next);
    card.append(icon, info, actions, menu);
    list.appendChild(card);
  });

  section.hidden = false;
  requestAnimationFrame(() => section.scrollIntoView({ behavior: "smooth", block: "nearest" }));
}

wireRunButtons = function enhancedWireRunButtons() {
  pawdfOriginalWireRunButtons();

  const wired = $('.run-btn[data-run="split"]');
  if (!wired) return;
  const clean = wired.cloneNode(true);
  wired.replaceWith(clean);
  renderSplitPlan();

  clean.addEventListener("click", () => {
    const [input] = filesFor("split");
    if (!input) return showToast("error", "Split", "Add a PDF first.");
    if (!splitUx.cuts.size) {
      return showToast("error", "Split", "Press at least one scissors button between pages.");
    }
    const ranges = splitSegments()
      .filter((segment) => splitUx.selected.has(segmentKey(segment)))
      .map(splitRangeText);
    if (!ranges.length) return showToast("error", "Split", "Select at least one output file.");
    setBusy("split", true, ranges.length > 1 ? `Creating ${ranges.length} files…` : "Creating file…");
    bridge.runSplit(input, JSON.stringify(ranges));
  });
};

wireSignals = function enhancedWireSignals() {
  pawdfOriginalWireSignals();
  const resultSignals = [
    ["split", bridge.splitFinished],
    ["merge", bridge.mergeFinished],
    ["organize", bridge.organizeFinished],
    ["rasterize", bridge.rasterizeFinished],
    ["imagepdf", bridge.imagepdfFinished],
    ["pdf_to_docx", bridge.pdfToWordFinished],
    ["docx_to_pdf", bridge.wordToPdfFinished],
    ["compress", bridge.compressFinished],
    ["rotate", bridge.rotateFinished],
    ["crop", bridge.cropFinished],
    ["repair", bridge.repairFinished],
    ["protect", bridge.protectFinished],
    ["unlock", bridge.unlockFinished],
    ["watermark", bridge.watermarkFinished],
    ["sign", bridge.signFinished],
    ["pagenumbers", bridge.pagenumbersFinished],
    ["pdf_to_markdown", bridge.markdownFinished],
    ["xlsx_to_pdf", bridge.xlsxToPdfFinished],
    ["pptx_to_pdf", bridge.pptxToPdfFinished],
    ["ocr", bridge.ocrFinished],
    ["forms", bridge.formsFinished],
    ["annotate", bridge.annotateFinished],
  ];
  resultSignals.forEach(([featureId, signal]) => {
    signal.connect((json) => showOperationResults(featureId, JSON.parse(json)));
  });
};

function setArrangeDropTarget(clientX, clientY) {
  clearDropMarkers();
  const element = document.elementFromPoint(clientX, clientY);
  const target = element && element.closest ? element.closest("#org-grid .thumb") : null;
  if (!target) {
    if (arrangePointer) arrangePointer.target = null;
    return;
  }
  const targetIndex = Number(target.dataset.index);
  const box = target.getBoundingClientRect();
  const after = clientX > box.left + box.width / 2;
  target.classList.add(after ? "drop-after" : "drop-before");
  if (arrangePointer) arrangePointer.target = { index: targetIndex, after };
}

function finishArrangePointer(event, cancelled = false) {
  if (!arrangePointer || arrangePointer.pointerId !== event.pointerId) return;
  const state = arrangePointer;
  arrangePointer = null;
  document.body.classList.remove("arrange-dragging");
  clearDropMarkers();
  try {
    if (state.item.hasPointerCapture(event.pointerId)) state.item.releasePointerCapture(event.pointerId);
  } catch (error) {
    /* The item may have been rebuilt already. */
  }
  state.item.classList.remove("dragging");

  if (!cancelled && state.dragging && state.target) {
    suppressArrangeClick = true;
    const to = state.target.after ? state.target.index + 1 : state.target.index;
    movePage(state.from, to);
    setTimeout(() => { suppressArrangeClick = false; }, 0);
  }
}

renderPages = function enhancedRenderPages() {
  const grid = $("#org-grid");
  grid.textContent = "";

  const hasPages = organize.pages.length > 0;
  $(".org-toolbar").hidden = !hasPages;
  $('.run-btn[data-run="organize"]').hidden = !hasPages;

  const selectedCount = organize.pages.filter((page) => page.selected).length;
  $(".org-count").textContent =
    plural(organize.pages.length, "page") +
    (selectedCount ? ` · ${selectedCount} selected` : " · drag pages directly to reorder");

  ["#org-move-l", "#org-move-r", "#org-rotate-l", "#org-rotate-r", "#org-delete"].forEach((id) => {
    $(id).disabled = selectedCount === 0;
  });

  if (!hasPages) {
    const empty = document.createElement("div");
    empty.className = "grid-status";
    empty.textContent = "Every page was deleted. Remove the file and add it again to start over.";
    grid.appendChild(empty);
    return;
  }

  organize.pages.forEach((page, index) => {
    const item = document.createElement("div");
    item.className = "thumb" + (page.selected ? " selected" : "");
    item.dataset.index = String(index);
    item.draggable = false;

    const dataUrl = thumbnailFor(page.originalIndex);
    if (dataUrl) {
      const image = document.createElement("img");
      image.src = dataUrl;
      image.alt = "";
      image.draggable = false;
      image.style.transform = `rotate(${page.rotation}deg)`;
      item.appendChild(image);
    } else {
      const fail = document.createElement("div");
      fail.className = "thumb-fail";
      fail.textContent = "...";
      item.appendChild(fail);
    }

    const label = document.createElement("div");
    label.className = "thumb-label";
    label.textContent = `Page ${page.originalIndex + 1}` + (page.rotation ? ` · ${page.rotation}°` : "");
    item.appendChild(label);

    item.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      arrangePointer = {
        pointerId: event.pointerId,
        from: index,
        startX: event.clientX,
        startY: event.clientY,
        item,
        dragging: false,
        target: null,
      };
      item.setPointerCapture(event.pointerId);
    });

    item.addEventListener("pointermove", (event) => {
      if (!arrangePointer || arrangePointer.pointerId !== event.pointerId) return;
      const distance = Math.hypot(
        event.clientX - arrangePointer.startX,
        event.clientY - arrangePointer.startY
      );
      if (!arrangePointer.dragging && distance < 6) return;
      if (!arrangePointer.dragging) {
        arrangePointer.dragging = true;
        item.classList.add("dragging");
        document.body.classList.add("arrange-dragging");
      }
      event.preventDefault();
      setArrangeDropTarget(event.clientX, event.clientY);
    });

    item.addEventListener("pointerup", (event) => finishArrangePointer(event));
    item.addEventListener("pointercancel", (event) => finishArrangePointer(event, true));

    item.addEventListener("click", (event) => {
      if (suppressArrangeClick) {
        event.preventDefault();
        return;
      }
      if (!event.shiftKey && !event.ctrlKey && !event.metaKey) {
        organize.pages.forEach((candidate) => {
          if (candidate !== page) candidate.selected = false;
        });
      }
      page.selected = !page.selected;
      renderPages();
    });

    grid.appendChild(item);
  });
};

/* PAWDF_STABLE_ORBIT_V2
   A single animation clock owns both transforms:
   - #ring-nodes rotates clockwise
   - every .upright rotates by the exact opposite angle in the same frame

   This preserves the circular movement while keeping every feature card and
   label upright, including after renderRing() replaces all node elements. */
const pawdfStableOrbit = {
  angle: 0,
  lastFrame: performance.now(),
  durationMs: 110000,
  frameId: 0,
  observer: null,
  reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)"),
};

function pawdfOrbitDurationMs() {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue("--orbit")
    .trim()
    .toLowerCase();

  const value = Number.parseFloat(raw);
  if (!Number.isFinite(value) || value <= 0) return 110000;
  return raw.endsWith("ms") ? value : value * 1000;
}

function pawdfApplyOrbitTransforms() {
  const container = document.querySelector("#ring-nodes");
  if (!container) return;

  const angle = pawdfStableOrbit.angle;
  container.style.transform = `rotate(${angle}deg)`;

  container.querySelectorAll(".upright").forEach((upright) => {
    upright.style.transform = `rotate(${-angle}deg)`;
  });
}

function pawdfOrbitIsPaused() {
  const ring = document.querySelector("#ring");
  return (
    !ring ||
    document.hidden ||
    ring.matches(":hover") ||
    document.body.classList.contains("tool-open") ||
    pawdfStableOrbit.reducedMotion.matches
  );
}

function pawdfOrbitFrame(now) {
  const elapsed = Math.max(
    0,
    Math.min(100, now - pawdfStableOrbit.lastFrame)
  );
  pawdfStableOrbit.lastFrame = now;

  if (!pawdfOrbitIsPaused()) {
    pawdfStableOrbit.angle =
      (pawdfStableOrbit.angle +
        (elapsed / pawdfStableOrbit.durationMs) * 360) %
      360;
  }

  pawdfApplyOrbitTransforms();
  pawdfStableOrbit.frameId = requestAnimationFrame(pawdfOrbitFrame);
}

function installPawdfStableOrbit() {
  const container = document.querySelector("#ring-nodes");
  if (!container || container.dataset.stableOrbit === "2") return;

  container.dataset.stableOrbit = "2";
  pawdfStableOrbit.durationMs = pawdfOrbitDurationMs();

  // renderRing() replaces every slot/upright node. Apply the current opposite
  // rotation immediately, rather than allowing even one visibly tilted frame.
  pawdfStableOrbit.observer = new MutationObserver(() => {
    pawdfApplyOrbitTransforms();
  });
  pawdfStableOrbit.observer.observe(container, {
    childList: true,
    subtree: true,
  });

  pawdfStableOrbit.reducedMotion.addEventListener?.("change", () => {
    pawdfStableOrbit.lastFrame = performance.now();
    pawdfApplyOrbitTransforms();
  });

  document.addEventListener("visibilitychange", () => {
    pawdfStableOrbit.lastFrame = performance.now();
  });

  pawdfApplyOrbitTransforms();
  pawdfStableOrbit.frameId = requestAnimationFrame(pawdfOrbitFrame);
}

installPawdfStableOrbit();

/* PAWDF_UX_HARDENING_V3
   Final interaction hardening layered on the UX upgrade. */

function closeContinueMenus(except = null) {
  $$("#results-list .continue-menu").forEach((menu) => {
    if (menu === except) return;
    menu.hidden = true;
    const trigger = menu.parentElement
      ? $(".result-continue", menu.parentElement)
      : null;
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  });
}

function arrangeScrollHost() {
  let node = $("#org-grid");
  while (node && node !== document.body) {
    const style = getComputedStyle(node);
    const scrollable = /(auto|scroll)/.test(style.overflowY) &&
      node.scrollHeight > node.clientHeight;
    if (scrollable) return node;
    node = node.parentElement;
  }
  return $(".detail-body");
}

function autoScrollArrange(clientY) {
  if (!arrangePointer || !arrangePointer.dragging) return;
  const host = arrangeScrollHost();
  if (!host) return;

  const box = host.getBoundingClientRect();
  const edge = Math.min(64, Math.max(36, box.height * 0.12));
  let delta = 0;
  if (clientY < box.top + edge) {
    delta = -Math.ceil(4 + 22 * (1 - (clientY - box.top) / edge));
  } else if (clientY > box.bottom - edge) {
    delta = Math.ceil(4 + 22 * (1 - (box.bottom - clientY) / edge));
  }
  if (!delta) return;

  const before = host.scrollTop;
  host.scrollTop += delta;
  if (host.scrollTop !== before) {
    requestAnimationFrame(() => {
      if (arrangePointer && arrangePointer.dragging) {
        setArrangeDropTarget(arrangePointer.lastX, arrangePointer.lastY);
      }
    });
  }
}

const pawdfHardeningClearResults = clearOperationResults;
clearOperationResults = function hardenedClearOperationResults() {
  closeContinueMenus();
  pawdfHardeningClearResults();
};

const pawdfHardeningShowResults = showOperationResults;
showOperationResults = function hardenedShowOperationResults(featureId, data) {
  closeContinueMenus();
  pawdfHardeningShowResults(featureId, data);
  const section = $("#operation-results");
  const title = $("#results-title");
  if (section) section.setAttribute("aria-live", "polite");
  if (title) title.setAttribute("tabindex", "-1");
};

const pawdfHardeningRefreshCutButtons = refreshSplitCutButtons;
refreshSplitCutButtons = function hardenedRefreshSplitCutButtons() {
  pawdfHardeningRefreshCutButtons();
  const clear = $("#split-clear-cuts");
  if (clear) clear.disabled = splitUx.cuts.size === 0;
};

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (!target.closest(".continue-menu") && !target.closest(".result-continue")) {
    closeContinueMenus();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  closeContinueMenus();
  if (arrangePointer) {
    finishArrangePointer({ pointerId: arrangePointer.pointerId }, true);
  }
});

document.addEventListener(
  "pointermove",
  (event) => {
    if (!arrangePointer || !arrangePointer.dragging) return;
    arrangePointer.lastX = event.clientX;
    arrangePointer.lastY = event.clientY;
    autoScrollArrange(event.clientY);
  },
  { passive: true }
);

window.addEventListener("blur", () => {
  if (arrangePointer) {
    finishArrangePointer({ pointerId: arrangePointer.pointerId }, true);
  }
});

const splitSummary = $("#split-summary");
if (splitSummary) splitSummary.setAttribute("aria-live", "polite");
refreshSplitCutButtons();
