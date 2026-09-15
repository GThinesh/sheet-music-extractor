/**
 * app.js — Music Sheet → PDF wizard.
 *
 * Supports:
 *   - Configurable sample interval & deduplication in Step 2.
 *   - Pairwise Compare View (Image 1 vs 2, Select or Cancel, with Undo) in Step 3.
 *   - Grid Gallery View in Step 3 (switchable anytime).
 *   - Edit & Arrange (reorder, vertical split, crop) in Step 4.
 *   - High-resolution A4 PDF generation in Step 5.
 */

// ── Helpers ──────────────────────────────────────────────────────────────

async function api(path, body = null) {
    const opts = body
        ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
        : { method: "GET" };
    const res = await fetch(path, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || "Request failed");
    }
    return res;
}

function show(el)   { el.hidden = false; }
function hide(el)   { el.hidden = true;  }
function $(sel)     { return document.querySelector(sel); }
function $$(sel)    { return [...document.querySelectorAll(sel)]; }

function setStatus(el, text, type = "") {
    el.textContent = text;
    el.className = "status" + (type ? " " + type : "");
}

function showSpinner(el) {
    el.innerHTML = "";
    el.className = "status spinner";
}

// ── State ────────────────────────────────────────────────────────────────

let allFrames = [];          // [{filename, timestamp_sec, timestamp_str}, ...]
let keptIndices = [];        // array of indexes into allFrames that are kept
let compareHistory = [];     // for undo: [{refIdx, candIdx, keptIndices}]
let curRefIdx = 0;           // left image index in pairwise compare
let curCandIdx = 1;          // right image index in pairwise compare
let editList = [];           // filenames for PDF generation

// ── Step 1: Download ─────────────────────────────────────────────────────

$("#btn-download").addEventListener("click", async () => {
    const url = $("#url-input").value.trim();
    if (!url) {
        alert("Please enter a YouTube video URL.");
        return;
    }
    const statusEl = $("#download-status");
    const btn = $("#btn-download");

    btn.disabled = true;
    showSpinner(statusEl);
    statusEl.textContent = "Downloading highest-resolution video… please wait.";

    try {
        const res = await api("/api/download", { url });
        const data = await res.json();
        setStatus(statusEl, `✓ Downloaded: "${data.title}" (${data.resolution})`, "ok");
        show($("#step-extract"));
        $("#step-extract").scrollIntoView({ behavior: "smooth" });
    } catch (e) {
        setStatus(statusEl, `✗ Download failed: ${e.message}`, "error");
    } finally {
        btn.disabled = false;
    }
});

// ── Step 2: Extract Frames ───────────────────────────────────────────────

$("#btn-extract").addEventListener("click", async () => {
    const statusEl = $("#extract-status");
    const btn = $("#btn-extract");

    const interval = parseFloat($("#sample-interval").value) || 5.0;
    const dedup = $("#chk-dedup").checked;
    const threshold = parseInt($("#dedup-threshold") ? $("#dedup-threshold").value : "7", 10) || 7;

    btn.disabled = true;
    showSpinner(statusEl);
    statusEl.textContent = `Extracting frames every ${interval}s (smart dedup: ${dedup ? "on (threshold " + threshold + ")" : "off"})…`;

    try {
        const res = await api("/api/extract", { interval, dedup, threshold });
        const data = await res.json();
        allFrames = data.frames;
        setStatus(statusEl, `✓ Extracted ${data.count} distinct frames for review.`, "ok");

        initStep3();
        show($("#step-select"));
        $("#step-select").scrollIntoView({ behavior: "smooth" });
    } catch (e) {
        setStatus(statusEl, `✗ Extraction failed: ${e.message}`, "error");
    } finally {
        btn.disabled = false;
    }
});

// Grey out threshold when dedup is off
$("#chk-dedup").addEventListener("change", (e) => {
    const sel = $("#dedup-threshold");
    if (sel) sel.disabled = !e.target.checked;
});

// ── Step 3: Selection Modes ──────────────────────────────────────────────

function initStep3() {
    curRefIdx = 0;
    curCandIdx = 1;
    compareHistory = [];

    // By default, first frame is the opening sheet music page
    keptIndices = allFrames.length > 0 ? [0] : [];

    renderComparePair();
    renderGalleryGrid();
    updateModeUI("compare");
}

// Mode switcher
$("#btn-mode-compare").addEventListener("click", () => updateModeUI("compare"));
$("#btn-mode-gallery").addEventListener("click", () => updateModeUI("gallery"));

function updateModeUI(mode) {
    if (mode === "compare") {
        $("#btn-mode-compare").classList.add("active");
        $("#btn-mode-gallery").classList.remove("active");
        show($("#compare-mode-container"));
        hide($("#gallery-mode-container"));
        renderComparePair();
    } else {
        $("#btn-mode-gallery").classList.add("active");
        $("#btn-mode-compare").classList.remove("active");
        hide($("#compare-mode-container"));
        show($("#gallery-mode-container"));
        syncGallerySelection();
    }
}

// ── Pairwise Compare Logic ───────────────────────────────────────────────

function renderComparePair() {
    const total = allFrames.length;
    const undoBtn = $("#btn-compare-undo");
    undoBtn.disabled = compareHistory.length === 0;

    if (total === 0) return;

    if (total === 1) {
        $("#compare-status-text").textContent = "Only 1 frame extracted. Ready to proceed.";
        $("#card-left").hidden = false;
        $("#card-right").hidden = true;
        $("#badge-left").textContent = `Page 1: ${allFrames[0].filename} (⏱ ${allFrames[0].timestamp_str})`;
        $("#img-compare-left").src = `/api/frames/${allFrames[0].filename}`;
        $("#btn-compare-cancel").disabled = true;
        $("#btn-compare-select").disabled = true;
        return;
    }

    if (curRefIdx >= total || curCandIdx >= total) {
        // Reached end of comparison
        $("#compare-status-text").textContent =
            `✓ Reviewed all ${total} frames! Total ${keptIndices.length} page(s) kept.`;
        $("#btn-compare-cancel").disabled = true;
        $("#btn-compare-select").disabled = true;
        return;
    }

    $("#btn-compare-cancel").disabled = false;
    $("#btn-compare-select").disabled = false;

    const refFrame = allFrames[curRefIdx];
    const candFrame = allFrames[curCandIdx];

    $("#compare-status-text").textContent =
        `Comparing: Image ${curRefIdx + 1} vs Image ${curCandIdx + 1}  ·  ${total} total frames  ·  ${keptIndices.length} page(s) kept`;

    $("#badge-left").textContent =
        `Reference: Image ${curRefIdx + 1} (⏱ ${refFrame.timestamp_str})`;
    $("#img-compare-left").src = `/api/frames/${refFrame.filename}`;

    $("#badge-right").textContent =
        `Candidate: Image ${curCandIdx + 1} (⏱ ${candFrame.timestamp_str})`;
    $("#img-compare-right").src = `/api/frames/${candFrame.filename}`;
}

// CANCEL Candidate (candidate is too similar / skip it)
$("#btn-compare-cancel").addEventListener("click", () => {
    if (curCandIdx >= allFrames.length) return;

    // Save history for Undo
    compareHistory.push({
        refIdx: curRefIdx,
        candIdx: curCandIdx,
        kept: [...keptIndices],
    });

    // Reference stays the same; candidate advances to next frame
    curCandIdx++;

    if (curCandIdx >= allFrames.length) {
        renderComparePair();
        proceedToStep4();
    } else {
        renderComparePair();
    }
});

// SELECT Candidate (candidate is a new music sheet page!)
$("#btn-compare-select").addEventListener("click", () => {
    if (curCandIdx >= allFrames.length) return;

    // Save history for Undo
    compareHistory.push({
        refIdx: curRefIdx,
        candIdx: curCandIdx,
        kept: [...keptIndices],
    });

    // Keep candidate
    if (!keptIndices.includes(curCandIdx)) {
        keptIndices.push(curCandIdx);
    }

    // Advance one step: the selected candidate becomes the new reference,
    // the next frame becomes the new candidate — every frame gets reviewed.
    curRefIdx = curCandIdx;
    curCandIdx = curCandIdx + 1;

    if (curCandIdx >= allFrames.length) {
        renderComparePair();
        proceedToStep4();
    } else {
        renderComparePair();
    }
});

// UNDO button
$("#btn-compare-undo").addEventListener("click", () => {
    if (compareHistory.length === 0) return;
    const prev = compareHistory.pop();
    curRefIdx = prev.refIdx;
    curCandIdx = prev.candIdx;
    keptIndices = prev.kept;
    renderComparePair();
});

// FINISH button
$("#btn-compare-finish").addEventListener("click", proceedToStep4);

// ── Gallery View Logic ───────────────────────────────────────────────────

function renderGalleryGrid() {
    const grid = $("#frame-grid");
    grid.innerHTML = "";

    allFrames.forEach((frame, idx) => {
        const card = document.createElement("div");
        card.className = "frame-card";
        card.dataset.idx = idx;

        const isSelected = keptIndices.includes(idx);
        if (isSelected) card.classList.add("selected");

        card.innerHTML = `
            <img src="/api/frames/${frame.filename}" alt="${frame.filename}" loading="lazy">
            <span class="time-tag">#${idx + 1} · ⏱ ${frame.timestamp_str}</span>
            <span class="check-icon">✓</span>
        `;

        card.addEventListener("click", () => {
            if (keptIndices.includes(idx)) {
                keptIndices = keptIndices.filter(i => i !== idx);
                card.classList.remove("selected");
            } else {
                keptIndices.push(idx);
                card.classList.add("selected");
            }
            updateGalleryCounter();
        });

        grid.appendChild(card);
    });

    updateGalleryCounter();
}

function syncGallerySelection() {
    $$(".frame-card").forEach(card => {
        const idx = +card.dataset.idx;
        if (keptIndices.includes(idx)) {
            card.classList.add("selected");
        } else {
            card.classList.remove("selected");
        }
    });
    updateGalleryCounter();
}

function updateGalleryCounter() {
    const count = keptIndices.length;
    $("#select-counter").textContent = `${count} selected`;
    $("#btn-proceed-gallery").disabled = (count === 0);
}

$("#btn-select-all").addEventListener("click", () => {
    keptIndices = allFrames.map((_, idx) => idx);
    syncGallerySelection();
});

$("#btn-deselect-all").addEventListener("click", () => {
    keptIndices = [];
    syncGallerySelection();
});

$("#btn-proceed-gallery").addEventListener("click", proceedToStep4);

// ── Transition to Step 4 ─────────────────────────────────────────────────

function proceedToStep4() {
    if (keptIndices.length === 0) {
        alert("Please select at least one page.");
        return;
    }

    // Sort kept indices in order
    const sorted = [...new Set(keptIndices)].sort((a, b) => a - b);
    editList = sorted.map(i => allFrames[i].filename);

    renderEditList();
    show($("#step-edit"));
    $("#step-edit").scrollIntoView({ behavior: "smooth" });
}

// ── Step 4: Edit & Arrange ───────────────────────────────────────────────

function renderEditList() {
    const list = $("#edit-list");
    list.innerHTML = "";

    if (editList.length === 0) {
        list.innerHTML = "<p class='status'>No pages selected. Please go back to Step 3.</p>";
        return;
    }

    editList.forEach((name, idx) => {
        const card = document.createElement("div");
        card.className = "edit-card";
        card.draggable = true;
        card.dataset.idx = idx;

        const isDeepInk = name.includes("_deepink_");
        const deepInkBadge = isDeepInk ? `<span class="badge-deepink" title="Variant 1: Deep Ink anti-aliasing applied">✨ Deep Ink</span>` : "";

        card.innerHTML = `
            <span class="drag-handle" title="Drag to reorder">⠿</span>
            <img src="/api/frames/${name}?t=${Date.now()}" alt="${name}">
            <div class="card-info">
                <span class="card-name">${name} ${deepInkBadge}</span>
                <span class="card-seq">Page ${idx + 1} of ${editList.length}</span>
            </div>
            <div class="card-actions">
                <button class="btn-deep-ink" title="Apply Variant 1: Deep Ink (removes watermark, crisp black notes)">${isDeepInk ? "✨ Re-apply Deep Ink" : "✨ Deep Ink"}</button>
                <button class="btn-split" title="Split into left and right parts at an adjustable position">✂ Split Vertical</button>
                <button class="btn-crop" title="Crop margins">✁ Crop</button>
                <button class="btn-remove danger" title="Remove page">✕ Remove</button>
            </div>
        `;

        // Drag & Drop
        card.addEventListener("dragstart", onDragStart);
        card.addEventListener("dragover",  onDragOver);
        card.addEventListener("drop",      onDrop);
        card.addEventListener("dragend",   onDragEnd);

        // Deep Ink
        card.querySelector(".btn-deep-ink").addEventListener("click", () => applyDeepInk(idx));

        // Split Vertical
        card.querySelector(".btn-split").addEventListener("click", () => splitImage(idx));

        // Crop
        card.querySelector(".btn-crop").addEventListener("click", () => openCropModal(idx));

        // Remove
        card.querySelector(".btn-remove").addEventListener("click", () => {
            editList.splice(idx, 1);
            renderEditList();
        });

        list.appendChild(card);
    });
}

// ── Drag & Drop ──────────────────────────────────────────────────────────

let dragSrcIdx = null;

function onDragStart(e) {
    dragSrcIdx = +e.currentTarget.dataset.idx;
    e.currentTarget.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
}

function onDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
}

function onDrop(e) {
    e.preventDefault();
    const targetIdx = +e.currentTarget.dataset.idx;
    if (dragSrcIdx === null || dragSrcIdx === targetIdx) return;

    const [moved] = editList.splice(dragSrcIdx, 1);
    editList.splice(targetIdx, 0, moved);
    renderEditList();
}

function onDragEnd(e) {
    e.currentTarget.classList.remove("dragging");
    dragSrcIdx = null;
}

// ── Deep Ink (Variant 1: Anti-Aliasing & Watermark Removal) ───────────────

async function applyDeepInk(idx) {
    const name = editList[idx];
    const btn = $$(".edit-card")[idx]?.querySelector(".btn-deep-ink");
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Processing…";
    }

    try {
        const res = await api("/api/deep-ink", { filename: name, bp: 60.0, wp: 205.0 });
        const data = await res.json();
        editList[idx] = data.cleaned;
        renderEditList();
    } catch (e) {
        alert("Deep Ink failed: " + e.message);
        if (btn) {
            btn.disabled = false;
            btn.textContent = "✨ Deep Ink";
        }
    }
}

async function applyDeepInkAll() {
    if (editList.length === 0) {
        alert("No pages to process.");
        return;
    }
    const btn = $("#btn-deep-ink-all");
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Processing all pages…";
    }

    try {
        for (let i = 0; i < editList.length; i++) {
            if (!editList[i].includes("_deepink_")) {
                const res = await api("/api/deep-ink", { filename: editList[i], bp: 60.0, wp: 205.0 });
                const data = await res.json();
                editList[i] = data.cleaned;
            }
        }
        renderEditList();
    } catch (e) {
        alert("Deep Ink batch failed: " + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "✨ Apply Deep Ink to All";
        }
    }
}

$("#btn-deep-ink-all")?.addEventListener("click", applyDeepInkAll);

// ── Split Vertical (adjustable divider) ──────────────────────────────────

let splitTargetIdx = null;

function splitImage(idx) {
    openSplitModal(idx);
}

function openSplitModal(idx) {
    splitTargetIdx = idx;
    const name = editList[idx];
    const imgEl = $("#split-image");
    imgEl.src = `/api/frames/${name}?t=${Date.now()}`;
    const slider = $("#split-slider");
    slider.value = "50";
    updateSplitDivider();
    show($("#split-modal"));
}

function updateSplitDivider() {
    const slider = $("#split-slider");
    const label = $("#split-value");
    const divider = $("#split-divider");
    const pct = parseInt(slider.value, 10) || 50;
    if (label) label.textContent = `${pct}%`;
    if (divider) divider.style.left = `${pct}%`;
}

$("#split-slider").addEventListener("input", updateSplitDivider);
$("#btn-split-cancel").addEventListener("click", closeSplitModal);
$("#split-modal .modal-backdrop").addEventListener("click", closeSplitModal);

function closeSplitModal() {
    hide($("#split-modal"));
    splitTargetIdx = null;
}

$("#btn-split-apply").addEventListener("click", async () => {
    if (splitTargetIdx === null) return;
    const name = editList[splitTargetIdx];
    const ratio = (parseInt($("#split-slider").value, 10) || 50) / 100;
    try {
        const res = await api("/api/split", { filename: name, ratio });
        const data = await res.json();
        // Replace original image with left then right part
        editList.splice(splitTargetIdx, 1, data.left, data.right);
        closeSplitModal();
        renderEditList();
    } catch (e) {
        alert("Split failed: " + e.message);
    }
});

// ── Crop Modal ───────────────────────────────────────────────────────────

let cropper = null;
let cropTargetIdx = null;

function openCropModal(idx) {
    cropTargetIdx = idx;
    const name = editList[idx];
    const imgEl = $("#crop-image");
    imgEl.src = `/api/frames/${name}?t=${Date.now()}`;
    show($("#crop-modal"));

    if (cropper) {
        cropper.destroy();
        cropper = null;
    }

    imgEl.addEventListener("load", function onLoad() {
        imgEl.removeEventListener("load", onLoad);
        // @ts-ignore
        cropper = new window.Cropper(imgEl, {
            viewMode: 1,
            autoCropArea: 1,
            responsive: true,
        });
    }, { once: true });
}

$("#btn-crop-cancel").addEventListener("click", closeCropModal);
$(".modal-backdrop").addEventListener("click", closeCropModal);

function closeCropModal() {
    hide($("#crop-modal"));
    if (cropper) {
        cropper.destroy();
        cropper = null;
    }
    cropTargetIdx = null;
}

$("#btn-crop-apply").addEventListener("click", async () => {
    if (!cropper || cropTargetIdx === null) return;
    const cropData = cropper.getData(true);
    const name = editList[cropTargetIdx];

    try {
        const res = await api("/api/crop", {
            filename: name,
            x: cropData.x,
            y: cropData.y,
            width: cropData.width,
            height: cropData.height,
        });
        const data = await res.json();
        editList[cropTargetIdx] = data.cropped;
        closeCropModal();
        renderEditList();
    } catch (e) {
        alert("Crop failed: " + e.message);
    }
});

// ── Step 5: Generate PDF ─────────────────────────────────────────────────

$("#btn-generate").addEventListener("click", async () => {
    if (editList.length === 0) {
        alert("Please select at least one page.");
        return;
    }

    const pageSize = $("#page-size") ? $("#page-size").value : "a4";
    const orientation = $("#page-orientation") ? $("#page-orientation").value : "portrait";

    const btn = $("#btn-generate");
    btn.disabled = true;
    const labelFor = (s, o) => `Generating ${s.toUpperCase()} ${o} PDF…`;
    btn.textContent = labelFor(pageSize, orientation);

    try {
        const res = await fetch("/api/generate-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ images: editList, page_size: pageSize, orientation }),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || "PDF generation failed");
        }

        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = `music_sheet_${pageSize}_${orientation}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(blobUrl);

        show($("#step-done"));
        $("#step-done").scrollIntoView({ behavior: "smooth" });

        // Ask if user wants to clean up output files
        setTimeout(() => {
            if (confirm("PDF generated successfully! Do you want to delete the temporary output files (video, frames, etc.) to save disk space?")) {
                cleanupOutput();
            }
        }, 1000);
    } catch (e) {
        alert("PDF error: " + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = "Generate PDF ↓";
    }
});

// ── Restart ──────────────────────────────────────────────────────────────

$("#btn-restart").addEventListener("click", () => {
    allFrames = [];
    keptIndices = [];
    compareHistory = [];
    editList = [];
    hide($("#step-extract"));
    hide($("#step-select"));
    hide($("#step-edit"));
    hide($("#step-done"));
    setStatus($("#download-status"), "");
    setStatus($("#extract-status"), "");
    $("#frame-grid").innerHTML = "";
    $("#edit-list").innerHTML = "";
    window.scrollTo({ top: 0, behavior: "smooth" });
});
