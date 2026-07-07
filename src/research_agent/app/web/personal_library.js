/**
 * P28 — Personal Library Browser Frontend
 * Handles: library item CRUD, BibTeX/Zotero import, annotations, reading list
 */

// ── State ───────────────────────────────────────────────────────────────────
let _libSelectedItemId = null;
let _libItems = [];
let _libCollections = [];
let _libAnnotations = [];
let _libReadingListItems = [];
let _libCheckedItems = new Set();

function _getAuthToken() {
  return localStorage.getItem("research_auth_token") || "";
}
function _authHeaders() {
  return { "Authorization": `Bearer ${_getAuthToken()}`, "Content-Type": "application/json" };
}
function _authHeadersPlain() {
  return { "Authorization": `Bearer ${_getAuthToken()}` };
}

// ── Tab Initialization ─────────────────────────────────────────────────────
async function loadLibraryBrowser() {
  if (document.querySelector("#libraryWorkbench")) {
    await Promise.all([_loadLibraryItems(), _loadLibraryFilters(), _loadReadingListStats()]);
  }
}

// ── Library Items ──────────────────────────────────────────────────────────
async function _loadLibraryItems(q, tag, col) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (tag) params.set("tags", tag);
  if (col) params.set("collections", col);
  params.set("limit", "200");

  // Clear multi-selection on list reload
  _libCheckedItems.clear();

  try {
    const res = await fetch(`/api/personal-library/items?${params}`, { headers: _authHeadersPlain() });
    if (!res.ok) throw new Error("Failed to load items");
    _libItems = await res.json();
    _renderLibraryList();
    _updateLibraryStats();
  } catch (err) {
    _setLibStatus(`Error: ${err.message}`);
  }
}

function _renderLibraryList() {
  const container = document.getElementById("libraryItemsContainer");
  const countEl = document.getElementById("libraryItemCount");
  if (!container) return;
  if (countEl) countEl.textContent = _libItems.length;

  if (_libItems.length === 0) {
    container.innerHTML = '<p class="small muted" style="padding: 20px; text-align: center;">No items found. Import BibTeX or Zotero references.</p>';
    _updateSelectionBar();
    return;
  }

  container.innerHTML = _libItems.map(item => {
    const authors = Array.isArray(item.authors) ? item.authors.join(", ") : item.authors || "";
    const year = item.year || item.published_at?.slice(0, 4) || "";
    const tags = Array.isArray(item.tags) ? item.tags.slice(0, 3) : [];
    const isSelected = item.id === _libSelectedItemId;
    const isChecked = _libCheckedItems.has(item.id);

    return `
      <div class="library-list-item ${isSelected ? "selected" : ""} ${isChecked ? "checked" : ""}" data-id="${item.id}">
        <div class="library-list-item-row">              <label class="lib-checkbox-label">
            <input type="checkbox" class="lib-item-checkbox" ${isChecked ? "checked" : ""} onchange="_toggleCheckItem('${item.id}', this.checked)" />
          </label>
          <div class="library-list-item-body" onclick="selectLibraryItem('${item.id}')">
            <div class="library-item-title">${_escapeHtml(item.title || "Untitled")}</div>
            <div class="library-item-meta">
              <span class="mono small">${_escapeHtml(authors)}</span>
              ${year ? `<span class="mono small" style="opacity: 0.6;">${year}</span>` : ""}
              <span class="mono small" style="opacity: 0.5;">${item.kind || "article"}</span>
            </div>
            <div class="library-item-tags">
              ${tags.map(t => `<span class="library-tag">${_escapeHtml(t)}</span>`).join("")}
              ${tags.length < (item.tags || []).length ? `<span class="library-tag more">+${(item.tags || []).length - tags.length}</span>` : ""}
            </div>
          </div>
        </div>
      </div>
    `;
  }).join("");
  _updateSelectionBar();
}

function _updateLibraryStats() {
  const el = document.getElementById("libraryStatsText");
  if (!el) return;
  const total = _libItems.length;
  const tagged = _libItems.filter(i => i.tags && i.tags.length > 0).length;
  el.textContent = `${total} items | ${tagged} tagged`;
}

function _setLibStatus(msg) {
  const el = document.getElementById("libraryStatsText");
  if (el) el.textContent = msg;
}

// ── Item Selection & Detail ────────────────────────────────────────────────
async function selectLibraryItem(itemId) {
  _libSelectedItemId = itemId;
  _renderLibraryList();

  const emptyEl = document.getElementById("libraryDetailEmpty");
  const contentEl = document.getElementById("libraryDetailContent");
  if (emptyEl) emptyEl.classList.add("hidden");
  if (contentEl) contentEl.classList.remove("hidden");

  // Find item in cache or fetch fresh
  let item = _libItems.find(i => i.id === itemId);
  if (!item) {
    try {
      const res = await fetch(`/api/personal-library/items/${itemId}`, { headers: _authHeadersPlain() });
      item = await res.json();
    } catch (err) {
      return;
    }
  }
  if (!item) return;

  // Metadata
  const titleEl = document.getElementById("libraryDetailTitle");
  const authorsEl = document.getElementById("libraryDetailAuthors");
  const venueEl = document.getElementById("libraryDetailVenue");
  const yearEl = document.getElementById("libraryDetailYear");
  const abstractEl = document.getElementById("libraryDetailAbstract");
  const doiLink = document.getElementById("libraryDetailDoi");
  const urlLink = document.getElementById("libraryDetailUrl");
  const arxivLink = document.getElementById("libraryDetailArxiv");
  const sourceEl = document.getElementById("libraryDetailSource");

  if (titleEl) titleEl.textContent = item.title || "Untitled";
  if (authorsEl) authorsEl.textContent = Array.isArray(item.authors) ? item.authors.join(", ") : item.authors || "Unknown authors";
  if (venueEl) {
    venueEl.textContent = item.venue ? `in ${item.venue}` : "";
    venueEl.style.display = item.venue ? "inline" : "none";
  }
  if (yearEl) yearEl.textContent = item.year || item.published_at?.slice(0, 4) || "";
  if (abstractEl) abstractEl.textContent = item.abstract || "No abstract available.";

  // Links
  if (doiLink) {
    if (item.doi) { doiLink.href = `https://doi.org/${item.doi}`; doiLink.classList.remove("hidden"); }
    else { doiLink.classList.add("hidden"); }
  }
  if (urlLink) {
    if (item.url) { urlLink.href = item.url; urlLink.classList.remove("hidden"); }
    else { urlLink.classList.add("hidden"); }
  }
  if (arxivLink) {
    if (item.arxiv_id) { arxivLink.href = `https://arxiv.org/abs/${item.arxiv_id}`; arxivLink.classList.remove("hidden"); }
    else { arxivLink.classList.add("hidden"); }
  }
  if (sourceEl) sourceEl.textContent = `Source: ${item.source || "manual"}`;

  // Store itemId for detail actions
  document.getElementById("libraryDetailContent")?.setAttribute("data-item-id", itemId);

  // Tags
  _renderTags(item.tags || []);
  _renderCollections(item.collections || []);
  _renderAnnotations(itemId);
  _renderReadingListForm(itemId);
}

function _renderTags(tags) {
  const el = document.getElementById("libraryDetailTags");
  if (!el) return;
  if (!tags || tags.length === 0) {
    el.innerHTML = '<span class="small muted">No tags</span>';
    return;
  }
  el.innerHTML = tags.map(t => `<span class="library-tag">${_escapeHtml(t)} <span class="library-tag-remove" onclick="_removeTag('${_escapeHtml(t)}')">&times;</span></span>`).join("");
}

function _renderCollections(collections) {
  const el = document.getElementById("libraryDetailCollections");
  if (!el) return;
  if (!collections || collections.length === 0) {
    el.innerHTML = '<span class="small muted">Not in any collection</span>';
    return;
  }
  el.innerHTML = collections.map(c => `<span class="library-collection-badge">${_escapeHtml(c)}</span>`).join("");
}

// ── Tags ───────────────────────────────────────────────────────────────────
async function _removeTag(tag) {
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const item = _libItems.find(i => i.id === itemId);
  if (!item) return;
  const newTags = (item.tags || []).filter(t => t !== tag);
  try {
    await fetch(`/api/personal-library/items/${itemId}`, {
      method: "PUT",
      headers: _authHeaders(),
      body: JSON.stringify({ tags: newTags })
    });
    item.tags = newTags;
    _renderTags(newTags);
  } catch (err) { console.error(err); }
}

async function _addTag() {
  const input = document.getElementById("libraryNewTagInput");
  const tag = input?.value?.trim();
  if (!tag) return;
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const item = _libItems.find(i => i.id === itemId);
  if (!item) return;
  const newTags = [...(item.tags || []), tag];
  try {
    await fetch(`/api/personal-library/items/${itemId}`, {
      method: "PUT",
      headers: _authHeaders(),
      body: JSON.stringify({ tags: newTags })
    });
    item.tags = newTags;
    _renderTags(newTags);
    input.value = "";
    document.getElementById("libraryAddTagRow")?.classList.add("hidden");
  } catch (err) { console.error(err); }
}

async function _autoTagItem() {
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const btn = document.getElementById("libraryAutoTagBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Tagging..."; }
  try {
    const res = await fetch(`/api/personal-library/items/${itemId}/auto-tag`, {
      method: "POST",
      headers: _authHeadersPlain()
    });
    const data = await res.json();
    if (data.tags) {
      const item = _libItems.find(i => i.id === itemId);
      if (item) item.tags = data.tags;
      _renderTags(data.tags);
    }
  } catch (err) { console.error(err); }
  if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Auto-Tag'; }
}

// ── Notes ──────────────────────────────────────────────────────────────────
function _editNotes() {
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const item = _libItems.find(i => i.id === itemId);
  const textarea = document.getElementById("libraryNotesTextarea");
  const notesEl = document.getElementById("libraryDetailNotes");
  const actionsEl = document.getElementById("libraryNotesActions");
  if (!textarea || !notesEl || !actionsEl) return;
  textarea.value = item?.notes || "";
  textarea.classList.remove("hidden");
  notesEl.classList.add("hidden");
  actionsEl.classList.remove("hidden");
}

async function _saveNotes() {
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const textarea = document.getElementById("libraryNotesTextarea");
  const notes = textarea?.value || "";
  try {
    await fetch(`/api/personal-library/items/${itemId}`, {
      method: "PUT",
      headers: _authHeaders(),
      body: JSON.stringify({ notes })
    });
    const item = _libItems.find(i => i.id === itemId);
    if (item) item.notes = notes;
    _cancelNotes();
  } catch (err) { console.error(err); }
}

function _cancelNotes() {
  const textarea = document.getElementById("libraryNotesTextarea");
  const notesEl = document.getElementById("libraryDetailNotes");
  const actionsEl = document.getElementById("libraryNotesActions");
  if (textarea) textarea.classList.add("hidden");
  if (notesEl) { notesEl.classList.remove("hidden"); notesEl.textContent = textarea?.value || "No notes."; }
  if (actionsEl) actionsEl.classList.add("hidden");
}

// ── Annotations ────────────────────────────────────────────────────────────
async function _renderAnnotations(itemId) {
  const container = document.getElementById("libraryAnnotationsList");
  const countEl = document.getElementById("libraryAnnotationCount");
  if (!container) return;
  try {
    const res = await fetch(`/api/personal-library/items/${itemId}/annotations`, { headers: _authHeadersPlain() });
    _libAnnotations = await res.json();
  } catch (err) {
    _libAnnotations = [];
  }
  if (countEl) countEl.textContent = _libAnnotations.length;

  if (_libAnnotations.length === 0) {
    container.innerHTML = '<p class="small muted">No annotations yet. Click "Add" to create one.</p>';
    return;
  }
  container.innerHTML = _libAnnotations.map(a => {
    const kindIcon = a.kind === "highlight" ? "🖍" : a.kind === "note" ? "📝" : a.kind === "comment" ? "💬" : "❓";
    return `
      <div class="annotation-card" style="border-left: 3px solid ${a.color || "#ffff00"};">
        <div class="annotation-header">
          <span>${kindIcon} ${a.kind}</span>
          <button class="btn-icon small" onclick="_deleteAnnotation('${a.id}')" title="Delete" style="padding: 2px 6px; font-size: 0.6rem;">&times;</button>
        </div>
        ${a.text ? `<div class="annotation-text">"${_escapeHtml(a.text)}"</div>` : ""}
        ${a.note ? `<div class="annotation-note">${_escapeHtml(a.note)}</div>` : ""}
        <div class="annotation-meta small muted">${a.created_at ? new Date(a.created_at).toLocaleDateString() : ""}</div>
      </div>
    `;
  }).join("");
}

function _showNewAnnotationForm() {
  document.getElementById("libraryNewAnnotationForm")?.classList.remove("hidden");
}

function _hideNewAnnotationForm() {
  document.getElementById("libraryNewAnnotationForm")?.classList.add("hidden");
  document.getElementById("libraryAnnText").value = "";
  document.getElementById("libraryAnnNote").value = "";
}

async function _saveAnnotation() {
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const kind = document.getElementById("libraryAnnKind")?.value || "highlight";
  const color = document.getElementById("libraryAnnColor")?.value || "#ffff00";
  const text = document.getElementById("libraryAnnText")?.value || "";
  const note = document.getElementById("libraryAnnNote")?.value || "";
  try {
    const params = new URLSearchParams();
    params.set("kind", kind);
    params.set("color", color);
    params.set("text", text);
    params.set("note", note);
    const res = await fetch(`/api/personal-library/items/${itemId}/annotations?${params}`, {
      method: "POST",
      headers: _authHeadersPlain()
    });
    if (res.ok) {
      _hideNewAnnotationForm();
      _renderAnnotations(itemId);
    }
  } catch (err) { console.error(err); }
}

async function _deleteAnnotation(annId) {
  const res = await fetch(`/api/personal-library/annotations/${annId}`, {
    method: "DELETE",
    headers: _authHeadersPlain()
  });
  if (res.ok) {
    const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
    if (itemId) _renderAnnotations(itemId);
  }
}

// ── Reading List ───────────────────────────────────────────────────────────
async function _renderReadingListForm(itemId) {
  try {
    const res = await fetch(`/api/personal-library/reading-list?status=`, { headers: _authHeadersPlain() });
    const entries = await res.json();
    const entry = entries.find(e => e.item_id === itemId);
    const statusEl = document.getElementById("libraryReadingStatus");
    const priorityEl = document.getElementById("libraryReadingPriority");
    const goalEl = document.getElementById("libraryReadingGoalDate");
    const progressEl = document.getElementById("libraryReadingProgress");
    const progressVal = document.getElementById("libraryReadingProgressVal");
    const saveBtn = document.getElementById("librarySaveReadingBtn");
    const removeBtn = document.getElementById("libraryRemoveReadingBtn");

    if (entry) {
      if (statusEl) statusEl.value = entry.status || "to_read";
      if (priorityEl) priorityEl.value = String(entry.priority || 0);
      if (goalEl) goalEl.value = entry.goal_date || "";
      if (progressEl) progressEl.value = entry.progress || 0;
      if (progressVal) progressVal.textContent = (entry.progress || 0) + "%";
      if (saveBtn) saveBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/></svg> Update Reading List';
      if (removeBtn) removeBtn.style.display = "inline-flex";
    } else {
      if (statusEl) statusEl.value = "to_read";
      if (priorityEl) priorityEl.value = "0";
      if (goalEl) goalEl.value = "";
      if (progressEl) progressEl.value = "0";
      if (progressVal) progressVal.textContent = "0%";
      if (saveBtn) saveBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/></svg> Save to Reading List';
      if (removeBtn) removeBtn.style.display = "none";
    }
  } catch (err) { console.error(err); }
}

async function _saveReadingListEntry() {
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const status = document.getElementById("libraryReadingStatus")?.value || "to_read";
  const priority = document.getElementById("libraryReadingPriority")?.value || "0";
  const goalDate = document.getElementById("libraryReadingGoalDate")?.value || "";
  const progress = document.getElementById("libraryReadingProgress")?.value || "0";

  try {
    // Try to update first
    const updateRes = await fetch(`/api/personal-library/reading-list/${itemId}`, {
      method: "PUT",
      headers: _authHeaders(),
      body: JSON.stringify({ status, priority: parseInt(priority), goal_date: goalDate, progress: parseInt(progress) })
    });
    if (!updateRes.ok) {
      // Create new entry
      await fetch(`/api/personal-library/reading-list/${itemId}?priority=${priority}&status=${status}${goalDate ? `&goal_date=${goalDate}` : ""}`, {
        method: "POST",
        headers: _authHeadersPlain()
      });
    }
    _loadReadingListStats();
  } catch (err) { console.error(err); }
}

async function _removeReadingListEntry() {
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  try {
    await fetch(`/api/personal-library/reading-list/${itemId}`, {
      method: "DELETE",
      headers: _authHeadersPlain()
    });
    _renderReadingListForm(itemId);
    _loadReadingListStats();
    // Refresh overlay if it's visible
    if (!document.getElementById("libraryReadingListPanel")?.classList.contains("hidden")) {
      _loadReadingListOverlay();
    }
  } catch (err) { console.error(err); }
}

async function _loadReadingListStats() {
  try {
    const res = await fetch("/api/personal-library/reading-list/stats", { headers: _authHeadersPlain() });
    if (!res.ok) return;
    const stats = await res.json();
    const toReadEl = document.getElementById("rlToReadCount");
    const readingEl = document.getElementById("rlReadingCount");
    const completedEl = document.getElementById("rlCompletedCount");
    const skippedEl = document.getElementById("rlSkippedCount");
    if (toReadEl) toReadEl.textContent = stats.to_read || 0;
    if (readingEl) readingEl.textContent = stats.reading || 0;
    if (completedEl) completedEl.textContent = stats.completed || 0;
    if (skippedEl) skippedEl.textContent = stats.skipped || 0;
  } catch (err) { /* ignore */ }
}

// ── Reading List Overlay ───────────────────────────────────────────────────
async function _loadReadingListOverlay() {
  const container = document.getElementById("rlItemsContainer");
  if (!container) return;
  const statusFilter = document.getElementById("rlStatusFilter")?.value || "";
  const search = document.getElementById("rlSearchInput")?.value?.toLowerCase() || "";

  try {
    const params = statusFilter ? `?status=${statusFilter}` : "";
    const res = await fetch(`/api/personal-library/reading-list${params}`, { headers: _authHeadersPlain() });
    const entries = await res.json();
    _libReadingListItems = entries;

    // Ensure library items are loaded for title resolution
    if (_libItems.length === 0 && entries.length > 0) {
      await _loadLibraryItems();
    }

    if (entries.length === 0) {
      container.innerHTML = '<p class="small muted" style="padding: 20px; text-align: center;">No entries in your reading list.</p>';
      return;
    }

    const filtered = search ? entries.filter(e => {
      const item = _libItems.find(i => i.id === e.item_id);
      const title = item?.title || "";
      return title.toLowerCase().includes(search);
    }) : entries;

    container.innerHTML = filtered.map(entry => {
      const item = _libItems.find(i => i.id === entry.item_id);
      const title = item?.title || "Unknown Item";
      const authors = Array.isArray(item?.authors) ? item.authors.join(", ") : "";
      const priorityNames = ["None", "Low", "Med-Low", "Medium", "High", "Critical"];
      const priorityLabel = priorityNames[entry.priority] || "None";
      const progress = entry.progress || 0;
      return `
        <div class="rl-item-card" onclick="selectLibraryItem('${entry.item_id}'); closeReadingListOverlay(); switchWorkbenchTab('library')">
          <div class="rl-item-top">
            <span class="rl-item-title">${_escapeHtml(title)}</span>
            <span class="rl-status-badge ${entry.status}">${entry.status === "reading" ? "📖" : entry.status === "completed" ? "✅" : entry.status === "skipped" ? "⏭" : "📋"}</span>
          </div>
          <div class="rl-item-meta mono small">${_escapeHtml(authors)}</div>
          <div class="rl-item-bottom">
            <div class="rl-progress-bar"><div class="rl-progress-fill" style="width: ${progress}%;"></div></div>
            <span class="rl-priority-label">${priorityLabel}</span>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<p class="small muted" style="padding: 20px; text-align: center;">Error: ${err.message}</p>`;
  }
}

function openReadingListOverlay() {
  const panel = document.getElementById("libraryReadingListPanel");
  if (panel) {
    panel.classList.remove("hidden");
    _loadReadingListOverlay();
  }
}

function closeReadingListOverlay() {
  document.getElementById("libraryReadingListPanel")?.classList.add("hidden");
}

// ── Import Modal ───────────────────────────────────────────────────────────
let _importMode = "bibtex";

function openLibraryImportModal() {
  _importMode = "bibtex";
  _switchImportTab("bibtex");
  document.getElementById("libraryImportModal")?.classList.remove("hidden");
  document.getElementById("libraryImportResult")?.classList.add("hidden");
}

function closeLibraryImportModal() {
  document.getElementById("libraryImportModal")?.classList.add("hidden");
}

function _switchImportTab(tab) {
  _importMode = tab;
  document.getElementById("importBibtexTab")?.classList.toggle("active", tab === "bibtex");
  document.getElementById("importZoteroTab")?.classList.toggle("active", tab === "zotero");
  document.getElementById("importFileTab")?.classList.toggle("active", tab === "file");
  document.getElementById("importBibtexBlock")?.classList.toggle("hidden", tab !== "bibtex");
  document.getElementById("importZoteroBlock")?.classList.toggle("hidden", tab !== "zotero");
  document.getElementById("importFileBlock")?.classList.toggle("hidden", tab !== "file");
}

async function _confirmImport() {
  const resultEl = document.getElementById("libraryImportResult");
  const confirmBtn = document.getElementById("libraryImportModalConfirm");
  if (confirmBtn) confirmBtn.disabled = true;
  if (resultEl) { resultEl.classList.remove("hidden"); resultEl.innerHTML = '<div class="modal-result-success"><p>Importing...</p></div>'; }

  try {
    let res;
    if (_importMode === "bibtex") {
      const content = document.getElementById("importBibtexTextarea")?.value;
      if (!content) { alert("Paste BibTeX content first."); return; }
      res = await fetch("/api/personal-library/import/bibtex", {
        method: "POST",
        headers: _authHeaders(),
        body: JSON.stringify({ content })
      });
    } else if (_importMode === "zotero") {
      const content = document.getElementById("importZoteroTextarea")?.value;
      if (!content) { alert("Paste Zotero JSON content first."); return; }
      res = await fetch("/api/personal-library/import/zotero", {
        method: "POST",
        headers: _authHeaders(),
        body: JSON.stringify({ content })
      });
    } else {
      const fileInput = document.getElementById("importFileInput");
      const file = fileInput?.files?.[0];
      if (!file) { alert("Select a file first."); return; }
      const formData = new FormData();
      formData.append("file", file);
      res = await fetch("/api/personal-library/import/file", {
        method: "POST",
        headers: { "Authorization": `Bearer ${_getAuthToken()}` },
        body: formData
      });
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Import failed");

    if (resultEl) resultEl.innerHTML = `<div class="modal-result-success"><p>✅ Successfully imported ${data.imported || 0} references.</p></div>`;
    setTimeout(() => { closeLibraryImportModal(); _loadLibraryItems(); }, 1500);
  } catch (err) {
    if (resultEl) resultEl.innerHTML = `<div class="modal-result-error"><p>Error: ${err.message}</p></div>`;
  } finally {
    if (confirmBtn) confirmBtn.disabled = false;
  }
}

// ── Filters ────────────────────────────────────────────────────────────────
async function _loadLibraryFilters() {
  try {
    // Load collections for filter and tag options
    const res = await fetch("/api/personal-library/collections", { headers: _authHeadersPlain() });
    _libCollections = await res.json();
    const colSelect = document.getElementById("libraryCollectionFilter");
    if (colSelect) {
      colSelect.innerHTML = '<option value="">All Collections</option>' +
        _libCollections.map(c => `<option value="${c.id}">${_escapeHtml(c.name)}</option>`).join("");
    }
  } catch (err) { /* ignore */ }

  // Collect tags from items
  const tagSet = new Set();
  _libItems.forEach(i => (i.tags || []).forEach(t => tagSet.add(t)));
  const tagSelect = document.getElementById("libraryTagFilter");
  if (tagSelect) {
    tagSelect.innerHTML = '<option value="">All Tags</option>' +
      Array.from(tagSet).sort().map(t => `<option value="${t}">${_escapeHtml(t)}</option>`).join("");
  }
}

// ── Delete Item ────────────────────────────────────────────────────────────
async function _deleteLibraryItem() {
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId || !confirm("Delete this item permanently?")) return;
  try {
    await fetch(`/api/personal-library/items/${itemId}`, {
      method: "DELETE",
      headers: _authHeadersPlain()
    });
    _libSelectedItemId = null;
    document.getElementById("libraryDetailContent")?.classList.add("hidden");
    document.getElementById("libraryDetailEmpty")?.classList.remove("hidden");
    _loadLibraryItems();
  } catch (err) { console.error(err); }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function _escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ── Collections Browser ─────────────────────────────────────────────────
let _collectionsData = [];
let _selectedCollectionId = null;

function openCollectionsOverlay() {
  const panel = document.getElementById("libraryCollectionsPanel");
  if (panel) {
    panel.classList.remove("hidden");
    _loadCollectionsBrowser();
  }
}

function closeCollectionsOverlay() {
  document.getElementById("libraryCollectionsPanel")?.classList.add("hidden");
  _selectedCollectionId = null;
}

async function _loadCollectionsBrowser() {
  try {
    const res = await fetch("/api/personal-library/collections", { headers: _authHeadersPlain() });
    if (!res.ok) throw new Error("Failed to load collections");
    _collectionsData = await res.json();
    _renderCollectionsList();
  } catch (err) {
    const container = document.getElementById("collectionsItemsContainer");
    if (container) container.innerHTML = `<p class="small muted" style="padding: 20px; text-align: center;">Error: ${err.message}</p>`;
  }
}

function _renderCollectionsList() {
  const container = document.getElementById("collectionsItemsContainer");
  const countEl = document.getElementById("collectionsCount");
  if (!container) return;
  if (countEl) countEl.textContent = _collectionsData.length;

  if (_collectionsData.length === 0) {
    container.innerHTML = '<p class="small muted" style="padding: 20px; text-align: center;">No collections yet. Create one to organize your items.</p>';
    return;
  }

  container.innerHTML = _collectionsData.map(col => {
    const isSelected = col.id === _selectedCollectionId;
    const itemCount = Array.isArray(col.item_ids) ? col.item_ids.length : 0;
    const isSmart = col.rules && col.rules.length > 0;
    return `
      <div class="collections-list-item ${isSelected ? "selected" : ""}" data-id="${col.id}" onclick="selectCollection('${col.id}')" style="border-left: 3px solid ${col.color || "#8b5cf6"};">
        <div class="collections-list-top">
          <span class="collections-list-icon">${col.icon || "📁"}</span>
          <div class="collections-list-info">
            <span class="collections-list-name">${_escapeHtml(col.name)}</span>
            <span class="collections-list-count mono small">${itemCount} items</span>
          </div>
          ${isSmart ? '<span class="collections-smart-badge">⚡ Smart</span>' : ''}
        </div>
        ${col.description ? `<div class="collections-list-desc">${_escapeHtml(col.description)}</div>` : ''}
      </div>
    `;
  }).join("");

  // Auto-select first if none selected
  if (!_selectedCollectionId && _collectionsData.length > 0) {
    selectCollection(_collectionsData[0].id);
  }
}

async function selectCollection(collectionId) {
  _selectedCollectionId = collectionId;
  _renderCollectionsList();

  const emptyEl = document.getElementById("collectionsDetailEmpty");
  const contentEl = document.getElementById("collectionsDetailContent");
  if (emptyEl) emptyEl.classList.add("hidden");
  if (contentEl) contentEl.classList.remove("hidden");

  // Fetch fresh collection detail
  let col;
  try {
    const res = await fetch(`/api/personal-library/collections/${collectionId}`, { headers: _authHeadersPlain() });
    col = await res.json();
  } catch (err) { return; }
  if (!col) return;

  document.getElementById("collectionsDetailContent")?.setAttribute("data-id", collectionId);

  // Header
  const iconEl = document.getElementById("collectionsDetailIcon");
  const nameEl = document.getElementById("collectionsDetailName");
  const metaEl = document.getElementById("collectionsDetailMeta");
  const descEl = document.getElementById("collectionsDetailDesc");
  const colorBar = document.getElementById("collectionsDetailColorBar");

  if (iconEl) iconEl.textContent = col.icon || "📁";
  if (nameEl) nameEl.textContent = col.name || "Untitled Collection";
  if (metaEl) metaEl.textContent = col.rules && col.rules.length > 0 ? "⚡ Smart Collection" : "📂 Manual Collection";
  if (descEl) descEl.textContent = col.description || "No description.";
  if (colorBar) colorBar.style.background = col.color || "#8b5cf6";

  // Rules
  _renderCollectionRules(col);

  // Members
  _renderCollectionMembers(col);
}

function _renderCollectionRules(col) {
  const container = document.getElementById("collectionsRulesList");
  const badge = document.getElementById("collectionsRulesBadge");
  const rulesSection = document.getElementById("collectionsRulesSection");
  if (!container || !rulesSection) return;

  const rules = col.rules || [];
  if (rules.length === 0) {
    rulesSection.style.display = "none";
    return;
  }
  rulesSection.style.display = "block";
  if (badge) badge.style.display = "inline-block";

  container.innerHTML = rules.map(r => {
    const opLabels = {
      equals: "=",
      contains: "contains",
      startswith: "starts with",
      regex: "matches",
      tag_contains: "tag contains",
      year_range: "year range",
    };
    return `
      <div class="collections-rule-row">
        <span class="collections-rule-field mono small">${_escapeHtml(r.field)}</span>
        <span class="collections-rule-op mono small">${opLabels[r.operator] || r.operator}</span>
        <span class="collections-rule-val mono small">"${_escapeHtml(r.value)}"</span>
      </div>
    `;
  }).join("");
}

async function _renderCollectionMembers(col) {
  const container = document.getElementById("collectionsMembersList");
  const countEl = document.getElementById("collectionsMemberCount");
  if (!container) return;

  const itemIds = col.item_ids || [];
  if (countEl) countEl.textContent = itemIds.length;

  if (itemIds.length === 0) {
    container.innerHTML = '<p class="small muted">No items in this collection.</p>';
    return;
  }

  // Fetch items to show titles/authors
  // Ensure library items are loaded
  if (_libItems.length === 0) {
    try {
      const res = await fetch("/api/personal-library/items?limit=200", { headers: _authHeadersPlain() });
      _libItems = await res.json();
    } catch (err) { _libItems = []; }
  }

  container.innerHTML = itemIds.map(id => {
    const item = _libItems.find(i => i.id === id);
    const title = item ? (item.title || "Untitled") : id;
    const authors = Array.isArray(item?.authors) ? item.authors.join(", ") : "";
    return `
      <div class="collections-member-item" onclick="_collectionsJumpToItem('${id}')">
        <div class="collections-member-title mono small">${_escapeHtml(title)}</div>
        <div class="collections-member-meta small muted">${_escapeHtml(authors)}</div>
      </div>
    `;
  }).join("");
}

function _collectionsJumpToItem(itemId) {
  closeCollectionsOverlay();
  selectLibraryItem(itemId);
}

// ── Collection Create/Edit Modal ─────────────────────────────────────────

let _editingCollectionId = null;

function _openCreateCollectionModal() {
  _editingCollectionId = null;
  document.getElementById("collectionModalTitle").textContent = "Create Collection";
  document.getElementById("libraryCollectionModalConfirm").textContent = "Save Collection";
  _resetCollectionModalForm();
  document.getElementById("libraryCollectionModal")?.classList.remove("hidden");
  document.getElementById("collectionModalStatus")?.classList.add("hidden");
}

function _openEditCollectionModal() {
  const col = _collectionsData.find(c => c.id === _selectedCollectionId);
  if (!col) return;
  _editingCollectionId = col.id;
  document.getElementById("collectionModalTitle").textContent = "Edit Collection";
  document.getElementById("libraryCollectionModalConfirm").textContent = "Update Collection";
  document.getElementById("libraryCollectionModal")?.classList.remove("hidden");
  document.getElementById("collectionModalStatus")?.classList.add("hidden");

  document.getElementById("collectionEditName").value = col.name || "";
  document.getElementById("collectionEditDesc").value = col.description || "";
  document.getElementById("collectionEditIcon").value = col.icon || "📁";
  document.getElementById("collectionEditColor").value = col.color || "#8b5cf6";
  const isDynamic = col.rules && col.rules.length > 0;
  document.getElementById("collectionEditIsDynamic").checked = isDynamic;

  _renderRulesEditList(col.rules || []);
  document.getElementById("collectionRulesEditor")?.classList.toggle("hidden", !isDynamic);
}

function _closeCollectionModal() {
  document.getElementById("libraryCollectionModal")?.classList.add("hidden");
  _editingCollectionId = null;
}

function _resetCollectionModalForm() {
  document.getElementById("collectionEditName").value = "";
  document.getElementById("collectionEditDesc").value = "";
  document.getElementById("collectionEditIcon").value = "📁";
  document.getElementById("collectionEditColor").value = "#8b5cf6";
  document.getElementById("collectionEditIsDynamic").checked = false;
  document.getElementById("collectionRulesEditor")?.classList.add("hidden");
  _editRules = [];
  _renderRulesEditList([]);
}

function _onCollectionDynamicToggle() {
  const isDynamic = document.getElementById("collectionEditIsDynamic")?.checked;
  document.getElementById("collectionRulesEditor")?.classList.toggle("hidden", !isDynamic);
}

// ── Rules Editor ─────────────────────────────────────────────────────────

function _renderRulesEditList(rules) {
  const container = document.getElementById("collectionRulesList");
  if (!container) return;

  if (!rules || rules.length === 0) {
    container.innerHTML = '<p class="small muted" style="padding: 8px 0;">No rules yet. Add rules to auto-filter items.</p>';
    return;
  }

  container.innerHTML = rules.map((r, i) => `
    <div class="collection-rule-edit-row" data-rule-index="${i}">
      <select class="rule-field-select library-filter-select" onchange="_updateRule(${i}, 'field', this.value)">
        <option value="title" ${r.field === "title" ? "selected" : ""}>Title</option>
        <option value="tags" ${r.field === "tags" ? "selected" : ""}>Tags</option>
        <option value="venue" ${r.field === "venue" ? "selected" : ""}>Venue</option>
        <option value="kind" ${r.field === "kind" ? "selected" : ""}>Type</option>
        <option value="published_at" ${r.field === "published_at" ? "selected" : ""}>Year</option>
        <option value="doi" ${r.field === "doi" ? "selected" : ""}>DOI</option>
        <option value="authors" ${r.field === "authors" ? "selected" : ""}>Authors</option>
        <option value="abstract" ${r.field === "abstract" ? "selected" : ""}>Abstract</option>
      </select>
      <select class="rule-operator-select library-filter-select" onchange="_updateRule(${i}, 'operator', this.value)">
        <option value="equals" ${r.operator === "equals" ? "selected" : ""}>=</option>
        <option value="contains" ${r.operator === "contains" ? "selected" : ""}>contains</option>
        <option value="startswith" ${r.operator === "startswith" ? "selected" : ""}>starts with</option>
        <option value="regex" ${r.operator === "regex" ? "selected" : ""}>regex</option>
        <option value="tag_contains" ${r.operator === "tag_contains" ? "selected" : ""}>tag contains</option>
        <option value="year_range" ${r.operator === "year_range" ? "selected" : ""}>year range</option>
      </select>
      <input type="text" class="rule-value-input library-tag-input" value="${_escapeHtml(r.value)}" placeholder="Value" onchange="_updateRule(${i}, 'value', this.value)" />
      <button class="btn-icon small" onclick="_removeRule(${i})" type="button" style="color: #f43f5e; padding: 4px 6px;">&times;</button>
    </div>
  `).join("");
}

let _editRules = [];

function _initEditRules(existingRules) {
  _editRules = (existingRules || []).map(r => ({ ...r }));
  _renderRulesEditList(_editRules);
}

function _addRule() {
  _editRules.push({ field: "tags", operator: "contains", value: "" });
  _renderRulesEditList(_editRules);
}

function _updateRule(index, key, value) {
  if (_editRules[index]) {
    _editRules[index][key] = value;
  }
}

function _removeRule(index) {
  _editRules.splice(index, 1);
  _renderRulesEditList(_editRules);
}

async function _saveCollection() {
  const name = document.getElementById("collectionEditName")?.value?.trim();
  if (!name) { _showCollectionModalStatus("Please enter a collection name.", "error"); return; }

  const description = document.getElementById("collectionEditDesc")?.value?.trim() || "";
  const icon = document.getElementById("collectionEditIcon")?.value?.trim() || "📁";
  const color = document.getElementById("collectionEditColor")?.value || "#8b5cf6";
  const isDynamic = document.getElementById("collectionEditIsDynamic")?.checked;

  // Only include non-empty rules for smart collections
  const rules = isDynamic ? _editRules.filter(r => r.field && r.value) : [];

  const confirmBtn = document.getElementById("libraryCollectionModalConfirm");
  if (confirmBtn) confirmBtn.disabled = true;

  try {
    let res;
    if (_editingCollectionId) {
      // Update existing
      res = await fetch(`/api/personal-library/collections/${_editingCollectionId}`, {
        method: "PUT",
        headers: _authHeaders(),
        body: JSON.stringify({ name, description, icon, color, rules })
      });
    } else {
      // Create new
      res = await fetch(`/api/personal-library/collections?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}&icon=${encodeURIComponent(icon)}`, {
        method: "POST",
        headers: _authHeaders(),
        body: JSON.stringify(rules.length > 0 ? rules : null)
      });
    }

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to save collection");
    }

    _showCollectionModalStatus("✅ Collection saved!", "success");
    setTimeout(() => {
      _closeCollectionModal();
      _loadCollectionsBrowser();
      _loadLibraryFilters(); // Refresh the collection filter dropdown
    }, 1000);
  } catch (err) {
    _showCollectionModalStatus(`Error: ${err.message}`, "error");
  } finally {
    if (confirmBtn) confirmBtn.disabled = false;
  }
}

async function _deleteCollection() {
  if (!_selectedCollectionId) return;
  const col = _collectionsData.find(c => c.id === _selectedCollectionId);
  const name = col?.name || "this collection";
  if (!confirm(`Delete "${name}"? Items in the collection will not be deleted.`)) return;

  try {
    const res = await fetch(`/api/personal-library/collections/${_selectedCollectionId}`, {
      method: "DELETE",
      headers: _authHeadersPlain()
    });
    if (!res.ok) throw new Error("Failed to delete");

    _selectedCollectionId = null;
    document.getElementById("collectionsDetailContent")?.classList.add("hidden");
    document.getElementById("collectionsDetailEmpty")?.classList.remove("hidden");
    _loadCollectionsBrowser();
    _loadLibraryFilters();
  } catch (err) {
    console.error(err);
  }
}

function _showCollectionModalStatus(msg, type) {
  const el = document.getElementById("collectionModalStatus");
  if (!el) return;
  el.classList.remove("hidden");
  el.textContent = msg;
  el.style.background = type === "error" ? "rgba(244,63,94,0.1)" : "rgba(52,211,153,0.1)";
  el.style.color = type === "error" ? "#fda4af" : "#6ee7b7";
  el.style.border = type === "error" ? "1px solid rgba(244,63,94,0.2)" : "1px solid rgba(52,211,153,0.2)";
}

// ── Multi-Format Export ─────────────────────────────────────────────────

const EXPORT_FORMATS = {
  bibtex: { endpoint: "/api/personal-library/export/bibtex", ext: ".bib", mime: "application/x-bibtex" },
  ris:    { endpoint: "/api/personal-library/export/ris",    ext: ".ris", mime: "application/x-ris" },
  "csl-json": { endpoint: "/api/personal-library/export/csl-json", ext: ".json", mime: "application/vnd.citationstyles.csl+json" },
};

async function _downloadExport(ids, format) {
  const fmt = EXPORT_FORMATS[format] || EXPORT_FORMATS.bibtex;
  const params = ids ? `?ids=${ids}` : "";
  const res = await fetch(`${fmt.endpoint}${params}`, {
    headers: { "Authorization": `Bearer ${_getAuthToken()}` }
  });
  if (!res.ok) throw new Error(`Failed to export ${format}: ${res.statusText}`);
  
  let blob;
  if (format === "csl-json") {
    // JSON endpoint returns structured JSON; re-serialize for consistent download
    const data = await res.json();
    blob = new Blob([JSON.stringify(data, null, 2)], { type: fmt.mime });
  } else {
    blob = await res.blob();
  }
  
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = ids ? `item${fmt.ext}` : `library-export${fmt.ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function _getExportFormat(selectId) {
  const sel = document.getElementById(selectId);
  return sel ? sel.value : "bibtex";
}

async function _exportItems(selectId) {
  // Toolbar / main export: checked items if any, otherwise ALL items
  const format = _getExportFormat(selectId);
  try {
    if (_libCheckedItems.size > 0) {
      const ids = Array.from(_libCheckedItems).join(",");
      await _downloadExport(ids, format);
      _clearSelection();
    } else {
      await _downloadExport(null, format);
    }
  } catch (err) {
    console.error("Export failed:", err);
    alert(`Export failed: ${err.message}`);
  }
}

async function _exportCheckedItems() {
  // Selection bar: export ONLY checked items
  const format = _getExportFormat("selExportFormat");
  try {
    if (_libCheckedItems.size === 0) { alert("No items selected."); return; }
    const ids = Array.from(_libCheckedItems).join(",");
    await _downloadExport(ids, format);
    _clearSelection();
  } catch (err) {
    console.error("Export failed:", err);
    alert(`Export failed: ${err.message}`);
  }
}

async function _exportSingleItem() {
  // Detail view: export the currently viewed item only
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const format = _getExportFormat("detailExportFormat");
  try {
    await _downloadExport(itemId, format);
  } catch (err) {
    console.error(err);
    alert(`Export failed: ${err.message}`);
  }
}

let _copyTimer = null;

async function _copyAsBibtex() {
  // Detail view: copy BibTeX for the current item to clipboard
  const itemId = document.getElementById("libraryDetailContent")?.getAttribute("data-item-id");
  if (!itemId) return;
  const btn = document.getElementById("libraryCopyBibtexBtn");
  const originalHtml = btn ? btn.innerHTML : "";
  if (_copyTimer) clearTimeout(_copyTimer);
  try {
    const res = await fetch(`/api/personal-library/export/bibtex?ids=${itemId}`, {
      headers: { "Authorization": `Bearer ${_getAuthToken()}` }
    });
    if (!res.ok) throw new Error("Failed to fetch BibTeX");
    const text = await res.text();
    await navigator.clipboard.writeText(text);
    if (btn) {
      btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg> Copied!';
      btn.style.color = "#34d399";
      _copyTimer = setTimeout(() => { btn.innerHTML = originalHtml; btn.style.color = ""; }, 2000);
    }
  } catch (err) {
    console.error("Copy failed:", err);
    if (btn) {
      btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg> Error';
      btn.style.color = "#f43f5e";
      _copyTimer = setTimeout(() => { btn.innerHTML = originalHtml; btn.style.color = ""; }, 2000);
    }
    alert(`Copy failed: ${err.message}`);
  }
}

// ── Multi-Select Checkbox Functions ────────────────────────────────────

function _toggleCheckItem(itemId, checked) {
  if (checked) {
    _libCheckedItems.add(itemId);
  } else {
    _libCheckedItems.delete(itemId);
  }
  // Update visual selection on items
  const itemEl = document.querySelector(`.library-list-item[data-id="${itemId}"]`);
  if (itemEl) itemEl.classList.toggle("checked", checked);
  _updateSelectionBar();
}

function _selectAllItems() {
  _libItems.forEach(item => _libCheckedItems.add(item.id));
  document.querySelectorAll(".lib-item-checkbox").forEach(cb => cb.checked = true);
  document.querySelectorAll(".library-list-item").forEach(el => el.classList.add("checked"));
  _updateSelectionBar();
}

function _clearSelection() {
  _libCheckedItems.clear();
  document.querySelectorAll(".lib-item-checkbox").forEach(cb => cb.checked = false);
  document.querySelectorAll(".library-list-item").forEach(el => el.classList.remove("checked"));
  _updateSelectionBar();
}

function _updateSelectionBar() {
  const bar = document.getElementById("libSelectionBar");
  const countEl = document.getElementById("libSelectedCount");
  if (!bar) return;
  const count = _libCheckedItems.size;
  if (count > 0) {
    bar.classList.remove("hidden");
    if (countEl) countEl.textContent = count;
  } else {
    bar.classList.add("hidden");
  }
}

// ── Progress slider ────────────────────────────────────────────────────────
function _updateProgress(val) {
  const el = document.getElementById("libraryReadingProgressVal");
  if (el) el.textContent = val + "%";
}

// ── Event Binding ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Search input
  const searchInput = document.getElementById("librarySearchInput");
  let searchTimer;
  searchInput?.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      _loadLibraryItems(searchInput.value, 
        document.getElementById("libraryTagFilter")?.value,
        document.getElementById("libraryCollectionFilter")?.value);
    }, 300);
  });

  // Filter dropdowns
  document.getElementById("libraryTagFilter")?.addEventListener("change", () => {
    _loadLibraryItems(
      document.getElementById("librarySearchInput")?.value,
      document.getElementById("libraryTagFilter")?.value,
      document.getElementById("libraryCollectionFilter")?.value
    );
  });
  document.getElementById("libraryCollectionFilter")?.addEventListener("change", () => {
    _loadLibraryItems(
      document.getElementById("librarySearchInput")?.value,
      document.getElementById("libraryTagFilter")?.value,
      document.getElementById("libraryCollectionFilter")?.value
    );
  });
  document.getElementById("libraryKindFilter")?.addEventListener("change", () => {
    _loadLibraryItems(
      document.getElementById("librarySearchInput")?.value,
      document.getElementById("libraryTagFilter")?.value,
      document.getElementById("libraryCollectionFilter")?.value
    );
  });

  // Import modal
  document.getElementById("libraryImportBtn")?.addEventListener("click", openLibraryImportModal);
  document.getElementById("libraryImportModalClose")?.addEventListener("click", closeLibraryImportModal);
  document.getElementById("libraryImportModalCancel")?.addEventListener("click", closeLibraryImportModal);
  document.getElementById("libraryImportModalConfirm")?.addEventListener("click", _confirmImport);
  document.getElementById("importBibtexTab")?.addEventListener("click", () => _switchImportTab("bibtex"));
  document.getElementById("importZoteroTab")?.addEventListener("click", () => _switchImportTab("zotero"));
  document.getElementById("importFileTab")?.addEventListener("click", () => _switchImportTab("file"));

  // Collections
  document.getElementById("libraryCollectionBtn")?.addEventListener("click", openCollectionsOverlay);
  document.getElementById("libraryCollectionsCloseBtn")?.addEventListener("click", closeCollectionsOverlay);
  document.getElementById("libraryCollectionsRefreshBtn")?.addEventListener("click", _loadCollectionsBrowser);
  document.getElementById("libraryCreateCollectionBtn")?.addEventListener("click", _openCreateCollectionModal);
  document.getElementById("collectionsEditBtn")?.addEventListener("click", _openEditCollectionModal);
  document.getElementById("collectionsDeleteBtn")?.addEventListener("click", _deleteCollection);

  // Collection modal
  document.getElementById("libraryCollectionModalClose")?.addEventListener("click", _closeCollectionModal);
  document.getElementById("libraryCollectionModalCancel")?.addEventListener("click", _closeCollectionModal);
  document.getElementById("libraryCollectionModalConfirm")?.addEventListener("click", _saveCollection);
  document.getElementById("collectionEditIsDynamic")?.addEventListener("change", _onCollectionDynamicToggle);
  document.getElementById("collectionAddRuleBtn")?.addEventListener("click", _addRule);

  // Close collections overlay when clicking outside
  document.getElementById("libraryCollectionsPanel")?.addEventListener("click", (e) => {
    if (e.target === document.getElementById("libraryCollectionsPanel")) closeCollectionsOverlay();
  });

  // Close collection modal when clicking outside
  document.getElementById("libraryCollectionModal")?.addEventListener("click", (e) => {
    if (e.target === document.getElementById("libraryCollectionModal")) _closeCollectionModal();
  });

  // Reading list
  document.getElementById("libraryReadingListBtn")?.addEventListener("click", openReadingListOverlay);
  document.getElementById("libraryReadingListCloseBtn")?.addEventListener("click", closeReadingListOverlay);
  document.getElementById("libraryReadingListRefreshBtn")?.addEventListener("click", _loadReadingListOverlay);
  document.getElementById("rlStatusFilter")?.addEventListener("change", _loadReadingListOverlay);
  document.getElementById("rlSearchInput")?.addEventListener("input", _loadReadingListOverlay);

  // Reading progress slider
  document.getElementById("libraryReadingProgress")?.addEventListener("input", (e) => _updateProgress(e.target.value));

  // Reading list actions in detail
  document.getElementById("librarySaveReadingBtn")?.addEventListener("click", _saveReadingListEntry);
  document.getElementById("libraryRemoveReadingBtn")?.addEventListener("click", _removeReadingListEntry);

  // Tags
  document.getElementById("libraryAutoTagBtn")?.addEventListener("click", _autoTagItem);
  document.getElementById("libraryAddTagBtn")?.addEventListener("click", () => {
    document.getElementById("libraryAddTagRow")?.classList.toggle("hidden");
  });
  document.getElementById("libraryConfirmTagBtn")?.addEventListener("click", _addTag);
  document.getElementById("libraryNewTagInput")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") _addTag();
  });

  // Notes
  document.getElementById("libraryEditNotesBtn")?.addEventListener("click", _editNotes);
  document.getElementById("librarySaveNotesBtn")?.addEventListener("click", _saveNotes);
  document.getElementById("libraryCancelNotesBtn")?.addEventListener("click", _cancelNotes);

  // Annotations
  document.getElementById("libraryAddAnnotationBtn")?.addEventListener("click", _showNewAnnotationForm);
  document.getElementById("librarySaveAnnotationBtn")?.addEventListener("click", _saveAnnotation);
  document.getElementById("libraryCancelAnnotationBtn")?.addEventListener("click", _hideNewAnnotationForm);

  // Multi-select
  document.getElementById("libSelectAllBtn")?.addEventListener("click", _selectAllItems);
  document.getElementById("libClearSelectionBtn")?.addEventListener("click", _clearSelection);
  document.getElementById("libExportCheckedBtn")?.addEventListener("click", _exportCheckedBibtex);

  // Export (multi-format)
  document.getElementById("libraryExportBtn")?.addEventListener("click", () => _exportItems("toolbarExportFormat"));
  document.getElementById("libExportCheckedBtn")?.addEventListener("click", _exportCheckedItems);
  document.getElementById("libraryExportSingleBtn")?.addEventListener("click", _exportSingleItem);
  document.getElementById("libraryCopyBibtexBtn")?.addEventListener("click", _copyAsBibtex);

  // Delete
  document.getElementById("libraryDeleteItemBtn")?.addEventListener("click", _deleteLibraryItem);

  // Refresh button
  document.getElementById("libraryRefreshBtn")?.addEventListener("click", () => _loadLibraryItems());

  // Close reading list overlay when clicking outside
  document.getElementById("libraryReadingListPanel")?.addEventListener("click", (e) => {
    if (e.target === document.getElementById("libraryReadingListPanel")) closeReadingListOverlay();
  });

  // Close import modal when clicking outside
  document.getElementById("libraryImportModal")?.addEventListener("click", (e) => {
    if (e.target === document.getElementById("libraryImportModal")) closeLibraryImportModal();
  });
});
