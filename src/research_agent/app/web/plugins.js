/**
 * P19 — Plugin System Browser Frontend
 * Handles: plugin listing, enable/disable, detail view, settings
 */

// ── State ───────────────────────────────────────────────────────────────────
let _pluginsData = [];
let _selectedPluginId = null;

function _getToken() {
  return localStorage.getItem("research_auth_token") || "";
}
function _authH() {
  return { "Authorization": `Bearer ${_getToken()}` };
}
function _authHJson() {
  return { "Authorization": `Bearer ${_getToken()}`, "Content-Type": "application/json" };
}

// ── Initialization ─────────────────────────────────────────────────────────
async function loadPluginsBrowser() {
  if (document.querySelector("#pluginsWorkbench")) {
    await _loadPlugins();
  }
}

// ── Plugin Loading ─────────────────────────────────────────────────────────
async function _loadPlugins() {
  const container = document.getElementById("pluginsItemsContainer");
  const countEl = document.getElementById("pluginsCountText");
  const enabledEl = document.getElementById("pluginsEnabledCount");
  const statusEl = document.getElementById("pluginsStatusText");
  if (!container) return;

  if (statusEl) statusEl.textContent = "Loading plugins...";
  try {
    const res = await fetch("/api/plugins", { headers: _authH() });
    if (!res.ok) throw new Error("Failed to load plugins");
    _pluginsData = await res.json();
    if (countEl) countEl.textContent = `${_pluginsData.length} plugins`;
    const enabledCount = _pluginsData.filter(p => p.enabled).length;
    if (enabledEl) enabledEl.textContent = `${enabledCount} enabled`;
    if (statusEl) statusEl.textContent = `Discovered ${_pluginsData.length} plugins, ${enabledCount} active`;

    _renderPluginsList();
  } catch (err) {
    if (statusEl) statusEl.textContent = `Error: ${err.message}`;
    container.innerHTML = `<p class="small muted" style="padding: 20px; text-align: center;">Error: ${err.message}</p>`;
  }
}

function _renderPluginsList() {
  const container = document.getElementById("pluginsItemsContainer");
  if (!container) return;
  if (_pluginsData.length === 0) {
    container.innerHTML = '<p class="small muted" style="padding: 20px; text-align: center;">No plugins discovered. Click "Rediscover" to scan for plugins.</p>';
    return;
  }
  container.innerHTML = _pluginsData.map(p => {
    const meta = p.metadata || {};
    const enabled = p.enabled;
    const isSelected = p.id === _selectedPluginId;
    const tags = (meta.tags || []).slice(0, 2);
    return `
      <div class="plugin-list-item ${isSelected ? "selected" : ""} ${enabled ? "enabled" : "disabled"}" data-id="${p.id}" onclick="selectPlugin('${p.id}')">
        <div class="plugin-list-top">
          <span class="plugin-list-name">${_esc(meta.name || p.id)}</span>
          <span class="plugin-status-dot ${enabled ? "active" : "inactive"}"></span>
        </div>
        <div class="plugin-list-desc">${_esc(meta.description || "No description")}</div>
        <div class="plugin-list-meta">
          <span class="mono small" style="opacity: 0.5;">v${meta.version || "0.0.0"}</span>
          ${tags.map(t => `<span class="plugin-tag">${_esc(t)}</span>`).join("")}
          <span class="mono small" style="opacity: ${enabled ? "0.7" : "0.4"}; margin-left: auto;">${enabled ? "Enabled" : "Disabled"}</span>
        </div>
      </div>
    `;
  }).join("");
}

// ── Plugin Selection ───────────────────────────────────────────────────────
async function selectPlugin(pluginId) {
  _selectedPluginId = pluginId;
  _renderPluginsList();

  document.getElementById("pluginsDetailEmpty")?.classList.add("hidden");
  document.getElementById("pluginsDetailContent")?.classList.remove("hidden");

  // Fetch detail
  try {
    const res = await fetch(`/api/plugins/${pluginId}`, { headers: _authH() });
    if (!res.ok) throw new Error("Plugin not found");
    const detail = await res.json();
    _renderPluginDetail(detail);
  } catch (err) {
    console.error(err);
  }
}

function _renderPluginDetail(detail) {
  const meta = detail.metadata || {};
  const enabled = detail.enabled;
  const nameEl = document.getElementById("pluginsDetailName");
  const versionEl = document.getElementById("pluginsDetailVersion");
  const descEl = document.getElementById("pluginsDetailDesc");
  const authorEl = document.getElementById("pluginsDetailAuthor");
  const hpEl = document.getElementById("pluginsDetailHomepage");
  const tagsEl = document.getElementById("pluginsDetailTags");
  const hooksEl = document.getElementById("pluginsDetailHooks");
  const toggleEl = document.getElementById("pluginsDetailToggle");
  const toggleStatus = document.getElementById("pluginsToggleStatus");
  const settingsSection = document.getElementById("pluginsSettingsSection");
  const settingsForm = document.getElementById("pluginsSettingsForm");
  const uiSection = document.getElementById("pluginsUiSection");
  const uiComponents = document.getElementById("pluginsUiComponents");

  if (nameEl) nameEl.textContent = meta.name || detail.id;
  if (versionEl) versionEl.textContent = `v${meta.version || "0.0.0"}`;
  if (descEl) descEl.textContent = meta.description || "No description available.";
  if (authorEl) authorEl.textContent = meta.author ? `By ${meta.author}` : "";
  if (hpEl) {
    if (meta.homepage) { hpEl.href = meta.homepage; hpEl.classList.remove("hidden"); }
    else { hpEl.classList.add("hidden"); }
  }

  // Tags
  if (tagsEl) {
    const tags = meta.tags || [];
    tagsEl.innerHTML = tags.length ? tags.map(t => `<span class="plugin-tag">${_esc(t)}</span>`).join("") : '<span class="small muted">No tags</span>';
  }

  // Hooks
  if (hooksEl) {
    const hooks = meta.hooks_implemented || [];
    const hookLabels = {
      on_run_start: "🚀 Run Start", on_section_generated: "📝 Section Generated",
      on_run_complete: "✅ Run Complete", on_error: "⚠️ Error", on_step: "👣 Step"
    };
    hooksEl.innerHTML = hooks.length
      ? hooks.map(h => `<span class="plugin-hook-badge">${hookLabels[h] || _esc(h)}</span>`).join("")
      : '<span class="small muted">No hooks implemented</span>';
  }

  // Toggle
  if (toggleEl) {
    toggleEl.checked = enabled;
    if (toggleStatus) toggleStatus.textContent = enabled ? "Enabled" : "Disabled";
    toggleEl.onchange = async () => {
      const endpoint = toggleEl.checked ? "enable" : "disable";
      try {
        await fetch(`/api/plugins/${detail.id}/${endpoint}`, { method: "POST", headers: _authHJson() });
        _loadPlugins();
      } catch (err) { console.error(err); }
    };
  }

  // Settings
  const schema = detail.settings_schema;
  if (schema && schema.properties && Object.keys(schema.properties).length) {
    settingsSection?.classList.remove("hidden");
    if (settingsForm) {
      settingsForm.innerHTML = Object.entries(schema.properties).map(([key, prop]) => {
        const currentVal = detail.settings?.[key] ?? prop.default ?? "";
        return `
          <div class="plugin-setting-row">
            <label class="plugin-setting-label">${_esc(prop.title || key)}</label>
            <input class="plugin-setting-input" data-key="${key}" value="${_esc(String(currentVal))}" placeholder="${_esc(prop.description || "")}" />
            ${prop.description ? `<span class="small muted">${_esc(prop.description)}</span>` : ""}
          </div>
        `;
      }).join("");
      // Add save button
      settingsForm.innerHTML += `
        <button id="pluginsSaveSettingsBtn" class="btn-icon primary" type="button" style="margin-top: 8px; padding: 6px 14px; font-size: 0.75rem;">Save Settings</button>
      `;
      document.getElementById("pluginsSaveSettingsBtn")?.addEventListener("click", () => _savePluginSettings(detail.id));
    }
  } else {
    settingsSection?.classList.add("hidden");
  }

  // UI Components
  const uiComps = detail.ui_components;
  if (uiComps && uiComps.length) {
    uiSection?.classList.remove("hidden");
    if (uiComponents) {
      uiComponents.innerHTML = uiComps.map(comp => `
        <div class="plugin-ui-card">
          <span class="plugin-ui-type">${_esc(comp.type || "component")}</span>
          <span class="plugin-ui-title">${_esc(comp.title || "")}</span>
          ${comp.render ? `<span class="mono small" style="opacity: 0.5;">render: ${_esc(comp.render)}</span>` : ""}
        </div>
      `).join("");
    }
  } else {
    uiSection?.classList.add("hidden");
  }
}

async function _savePluginSettings(pluginId) {
  const settings = {};
  document.querySelectorAll(".plugin-setting-input").forEach(el => {
    settings[el.dataset.key] = el.value;
  });
  try {
    await fetch(`/api/plugins/${pluginId}/settings`, {
      method: "PUT", headers: _authHJson(), body: JSON.stringify(settings)
    });
    const btn = document.getElementById("pluginsSaveSettingsBtn");
    if (btn) { btn.textContent = "Saved ✓"; setTimeout(() => { btn.textContent = "Save Settings"; }, 2000); }
  } catch (err) { console.error(err); }
}

// ── Rediscover ─────────────────────────────────────────────────────────────
async function _rediscoverPlugins() {
  const btn = document.getElementById("pluginsRediscoverBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Discovering..."; }
  try {
    await fetch("/api/plugins/discover", { method: "POST", headers: _authHJson() });
    await _loadPlugins();
  } catch (err) { console.error(err); }
  if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg> Rediscover'; }
}

// ── Helper ─────────────────────────────────────────────────────────────────
function _esc(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ── Event Binding ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("pluginsRediscoverBtn")?.addEventListener("click", _rediscoverPlugins);
  document.getElementById("pluginsRefreshBtn")?.addEventListener("click", _loadPlugins);
});
