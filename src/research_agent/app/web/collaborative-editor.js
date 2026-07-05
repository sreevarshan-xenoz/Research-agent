/**
 * P25: Collaborative Real-Time Co-Editing
 *
 * Integrates Yjs CRDT with Quill.js for real-time collaborative editing.
 * Provides cursor presence, section locking, comment threads, and version history.
 *
 * Usage:
 *   CollabEditor.init(quillInstance, { docName: "run-abc123" });
 */

(function () {
  "use strict";

  const CollabEditor = {
    // ── State ────────────────────────────────────────────────
    ydoc: null,
    ytext: null,
    provider: null,
    awareness: null,
    binding: null,
    connected: false,
    docName: null,
    userColor: "#8b5cf6",
    lockToken: null,
    lockSection: null,
    quill: null,
    apiBase: "/api/collab",
    dom: {},

    // ── Initialize ───────────────────────────────────────────
    init: function (quillInstance, options) {
      if (!quillInstance) {
        console.warn("[Collab] No Quill instance provided");
        return;
      }

      this.quill = quillInstance;
      this.docName = options?.docName || "default";
      this.userColor = this._getUserColor();

      this.dom = {
        statusEl: document.getElementById("collabStatus"),
        indicator: document.getElementById("collabIndicator"),
        lockSectionSelect: document.getElementById("collabSectionSelect"),
        lockBtn: document.getElementById("collabLockBtn"),
        commentsPanel: document.getElementById("collabCommentsPanel"),
        commentsList: document.getElementById("collabCommentsList"),
        commentInput: document.getElementById("collabCommentInput"),
        commentSubmitBtn: document.getElementById("collabCommentSubmit"),
        versionPanel: document.getElementById("collabVersionPanel"),
        versionList: document.getElementById("collabVersionList"),
        createSnapshotBtn: document.getElementById("collabCreateSnapshotBtn"),
      };

      if (options?.autoConnect !== false) {
        this.connect();
      }

      this._setupListeners();
      console.log("[Collab] Initialized for", this.docName);
    },

    // ── Connect to Yjs Document ─────────────────────────────
    connect: function () {
      this._setStatus("connecting", "Connecting...");

      const Y = window.Y;
      const WebsocketProvider = window.WebsocketProvider;
      const QuillBinding = window.QuillBinding;

      if (!Y || !WebsocketProvider || !QuillBinding) {
        this._setStatus("error", "Loading Yjs libraries...");
        this._loadLibs();
        return;
      }

      try {
        // Clean up previous session
        this._disconnect();

        this.ydoc = new Y.Doc();
        this.ytext = this.ydoc.getText("quill");

        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = proto + "//" + window.location.host + "/api/collab/ws";

        this.provider = new WebsocketProvider(wsUrl, this.docName, this.ydoc, {
          connect: true,
          maxBackoff: 5000,
        });

        this.awareness = this.provider.awareness;
        this.awareness.setLocalStateField("user", {
          name: this._getDisplayName(),
          color: this.userColor,
        });

        // Cursor module is already registered in app.js before Quill creation
        if (this.quill.getModule && !this.quill.getModule("cursors")) {
          console.warn("[Collab] Cursors module not available; cursor presence disabled");
        }

        this.binding = new QuillBinding(this.ytext, this.quill, this.awareness);

        this.provider.on("status", (event) => {
          this.connected = event.status === "connected";
          if (this.connected) {
            const count = this.awareness.getStates().size;
            this._setStatus("connected", "Connected (" + count + " user" + (count !== 1 ? "s" : "") + ")");
            this._updateIndicator(count);
          } else {
            this._setStatus("connecting", event.status);
            this._updateIndicator(0);
          }
        });

        this.awareness.on("change", () => {
          if (this.connected && this.dom.statusEl) {
            const count = this.awareness.getStates().size;
            this.dom.statusEl.textContent = "Connected (" + count + " user" + (count !== 1 ? "s" : "") + ")";
            this._updateIndicator(count);
          }
        });

        this._setStatus("connected", "Connected");
      } catch (err) {
        console.error("[Collab] Connection error:", err);
        this._setStatus("error", err.message);
      }
    },

    _disconnect: function () {
      if (this.provider) {
        this.provider.disconnect();
        this.provider = null;
      }
      if (this.binding) {
        this.binding.destroy();
        this.binding = null;
      }
      if (this.awareness) {
        this.awareness.destroy();
        this.awareness = null;
      }
      this.ydoc = null;
      this.ytext = null;
      this.connected = false;
    },

    disconnect: function () {
      this._disconnect();
      this._setStatus("disconnected", "Disconnected");
      this._updateIndicator(0);
      if (this.lockToken) {
        this.releaseLock(this.lockSection);
      }
    },

    // ── Lazy-load Yjs libraries from CDN (sequential, dependency-aware) ──
    _loadLibs: function () {
      var self = this;

      // Load Yjs first (foundational dependency)
      function loadYjs() {
        if (window.Y) { loadWebsocket(); return; }
        var s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/yjs@13.6.21/dist/yjs.cjs.min.js";
        s.onload = loadWebsocket;
        s.onerror = function () { self._setStatus("error", "Failed to load Yjs"); };
        document.head.appendChild(s);
      }

      // Then y-websocket provider (depends on Y)
      function loadWebsocket() {
        if (window.WebsocketProvider) { loadYQuill(); return; }
        var s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/y-websocket@3.0.3/dist/y-websocket.cjs.min.js";
        s.onload = loadYQuill;
        s.onerror = function () { self._setStatus("error", "Failed to load y-websocket"); };
        document.head.appendChild(s);
      }

      // Then y-quill binding (depends on Y)
      function loadYQuill() {
        if (window.QuillBinding) { loadCursors(); return; }
        var s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/y-quill@1.0.0/dist/y-quill.cjs.min.js";
        s.onload = loadCursors;
        s.onerror = function () { self._setStatus("error", "Failed to load y-quill"); };
        document.head.appendChild(s);
      }

      // QuillCursors is loaded via index.html CDN (before app.js).
      // Try dynamic load only if not already available (e.g. offline).
      function loadCursors() {
        if (window.QuillCursors) { 
          // Fallback register if app.js didn't do it yet
          if (window.Quill && window.Quill.register) {
            try { window.Quill.register('modules/cursors', window.QuillCursors); } catch (e) {}
          }
          self._setStatus("connecting", "Libraries loaded, connecting..."); 
          self.connect(); 
          return; 
        }
        var s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/quill-cursors@4.0.3/dist/quill-cursors.min.js";
        s.onload = function () {
          try {
            if (window.Quill && window.QuillCursors) {
              window.Quill.register('modules/cursors', window.QuillCursors);
            }
          } catch (e) { /* Non-critical */ }
          self._setStatus("connecting", "Libraries loaded, connecting...");
          self.connect();
        };
        s.onerror = function () { self._setStatus("connecting", "Continuing without cursors..."); self.connect(); };
        document.head.appendChild(s);
      }

      loadYjs();
    },

    // ── Section Locking ─────────────────────────────────────
    acquireLock: async function (sectionId) {
      if (!this.docName) return null;
      var self = this;
      try {
        var res = await fetch(this.apiBase + "/locks/acquire", {
          method: "POST",
          headers: this._authHeaders(),
          body: JSON.stringify({ doc_name: this.docName, section_id: sectionId }),
        });
        if (!res.ok) {
          if (res.status === 409) {
            this._setStatus("locked", "Section locked by another user");
          }
          return null;
        }
        var data = await res.json();
        this.lockToken = data.token;
        this.lockSection = sectionId;
        this._setStatus("locked", "Editing: " + sectionId);
        return data;
      } catch (err) {
        console.error("[Collab] Lock error:", err);
        return null;
      }
    },

    releaseLock: async function (sectionId) {
      if (!this.lockToken) return;
      try {
        await fetch(this.apiBase + "/locks/release", {
          method: "POST",
          headers: this._authHeaders(),
          body: JSON.stringify({
            doc_name: this.docName,
            section_id: sectionId || this.lockSection,
            lock_token: this.lockToken,
          }),
        });
      } catch (err) {
        console.error("[Collab] Release lock error:", err);
      }
      this.lockToken = null;
      this.lockSection = null;
      if (this.connected) {
        this._setStatus("connected", "Connected");
      }
    },

    _authHeaders: function () {
      var headers = { "Content-Type": "application/json" };
      var token = localStorage.getItem("research_auth_token");
      if (token) headers["Authorization"] = "Bearer " + token;
      return headers;
    },

    // ── Comments ────────────────────────────────────────────
    addComment: async function (sectionId, text) {
      if (!text.trim()) return null;
      try {
        var res = await fetch(this.apiBase + "/comments", {
          method: "POST",
          headers: this._authHeaders(),
          body: JSON.stringify({ doc_name: this.docName, section_id: sectionId, text: text.trim() }),
        });
        return res.ok ? await res.json() : null;
      } catch (err) {
        return null;
      }
    },

    loadComments: async function (sectionId) {
      if (!this.docName) return [];
      try {
        var res = await fetch(this.apiBase + "/comments/" + this.docName + "/" + sectionId);
        if (!res.ok) return [];
        var data = await res.json();
        return data.comments || [];
      } catch (err) {
        return [];
      }
    },

    resolveComment: async function (commentId, sectionId) {
      try {
        var res = await fetch(this.apiBase + "/comments/resolve", {
          method: "POST",
          headers: this._authHeaders(),
          body: JSON.stringify({ doc_name: this.docName, section_id: sectionId, comment_id: commentId }),
        });
        return res.ok;
      } catch (err) {
        return false;
      }
    },

    // ── Version History ─────────────────────────────────────
    createSnapshot: async function (label) {
      if (!this.ytext || !this.docName) return null;
      try {
        var res = await fetch(this.apiBase + "/versions", {
          method: "POST",
          headers: this._authHeaders(),
          body: JSON.stringify({
            doc_name: this.docName,
            label: label || "Snapshot " + new Date().toLocaleString(),
            content: this.ytext.toString(),
          }),
        });
        return res.ok ? await res.json() : null;
      } catch (err) {
        return null;
      }
    },

    listSnapshots: async function () {
      if (!this.docName) return [];
      try {
        var res = await fetch(this.apiBase + "/versions/" + this.docName);
        if (!res.ok) return [];
        var data = await res.json();
        return data.snapshots || [];
      } catch (err) {
        return [];
      }
    },

    rollback: async function (snapshotId) {
      try {
        var res = await fetch(this.apiBase + "/versions/rollback", {
          method: "POST",
          headers: this._authHeaders(),
          body: JSON.stringify({ doc_name: this.docName, snapshot_id: snapshotId }),
        });
        if (!res.ok) return null;
        return await res.json();
      } catch (err) {
        return null;
      }
    },

    // ── UI Helpers ──────────────────────────────────────────
    _setStatus: function (status, text) {
      if (this.dom.statusEl) {
        this.dom.statusEl.className = "collab-status " + status;
        this.dom.statusEl.textContent = text;
      }
    },

    _updateIndicator: function (count) {
      if (!this.dom.indicator) return;
      if (count > 0) {
        this.dom.indicator.innerHTML = '<span class="live-dot"></span> ' + count + ' user' + (count !== 1 ? "s" : "");
        this.dom.indicator.className = "collab-indicator active";
      } else {
        this.dom.indicator.textContent = "Offline";
        this.dom.indicator.className = "collab-indicator";
      }
    },

    _getUserColor: function () {
      var colors = ["#4285F4", "#EA4335", "#FBBC05", "#34A853", "#8F00FF", "#00BCD4", "#FF4081", "#7C4DFF"];
      var uid = localStorage.getItem("research_user_id") || "anon";
      var hash = 0;
      for (var i = 0; i < uid.length; i++) {
        hash = uid.charCodeAt(i) + ((hash << 5) - hash);
      }
      return colors[Math.abs(hash) % colors.length];
    },

    _getDisplayName: function () {
      var stored = localStorage.getItem("research_user_name");
      if (stored) return stored;
      var uid = localStorage.getItem("research_user_id") || "anon";
      var names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"];
      var hash = uid.split("").reduce(function (a, c) { return a + c.charCodeAt(0); }, 0);
      return names[hash % names.length] + "-" + uid.slice(0, 4);
    },

    // ── Event Listeners ─────────────────────────────────────
    _setupListeners: function () {
      var self = this;

      // Lock button
      if (this.dom.lockBtn && this.dom.lockSectionSelect) {
        this.dom.lockBtn.addEventListener("click", async function () {
          var section = self.dom.lockSectionSelect.value;
          if (!section) return;
          if (self.lockSection === section) {
            await self.releaseLock(section);
            self.dom.lockBtn.textContent = "Lock Section";
            self.dom.lockBtn.classList.remove("locked");
          } else {
            if (self.lockSection) await self.releaseLock(self.lockSection);
            var result = await self.acquireLock(section);
            if (result) {
              self.dom.lockBtn.textContent = "Editing " + section;
              self.dom.lockBtn.classList.add("locked");
            }
          }
        });
      }

      // Comment submit
      if (this.dom.commentSubmitBtn && this.dom.commentInput) {
        this.dom.commentSubmitBtn.addEventListener("click", async function () {
          var text = self.dom.commentInput.value;
          var section = self.dom.lockSectionSelect ? self.dom.lockSectionSelect.value : "general";
          if (!text.trim()) return;
          var result = await self.addComment(section, text);
          if (result) {
            self.dom.commentInput.value = "";
            self._refreshComments(section);
          }
        });

        this.dom.commentInput.addEventListener("keydown", function (e) {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            self.dom.commentSubmitBtn.click();
          }
        });
      }

      // Create snapshot
      if (this.dom.createSnapshotBtn) {
        this.dom.createSnapshotBtn.addEventListener("click", async function () {
          var label = prompt("Snapshot label (optional):");
          var result = await self.createSnapshot(label || undefined);
          if (result) self._refreshVersionList();
        });
      }
    },

    _refreshComments: async function (sectionId) {
      if (!this.dom.commentsList) return;
      var comments = await this.loadComments(sectionId);
      var self = this;

      if (comments.length === 0) {
        this.dom.commentsList.innerHTML = '<p class="small muted">No comments yet.</p>';
        return;
      }

      this.dom.commentsList.innerHTML = comments.map(function (c) {
        var date = new Date(c.created_at * 1000).toLocaleString();
        return (
          '<div class="collab-comment' + (c.resolved ? " resolved" : "") + '" data-id="' + c.id + '">' +
            '<div class="comment-header">' +
              '<span class="comment-author">' + (c.user_display || "Anonymous") + "</span>" +
              '<span class="comment-time">' + date + "</span>" +
            "</div>" +
            '<div class="comment-text">' + self._escape(c.text) + "</div>" +
            '<div class="comment-actions">' +
              (!c.resolved
                ? '<button class="comment-resolve-btn" data-id="' + c.id + '">Resolve</button>'
                : '<span class="resolved-badge">\u2713 Resolved</span>') +
            "</div>" +
          "</div>"
        );
      }).join("");

      this.dom.commentsList.querySelectorAll(".comment-resolve-btn").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          await self.resolveComment(btn.dataset.id, sectionId);
          self._refreshComments(sectionId);
        });
      });
    },

    _refreshVersionList: async function () {
      if (!this.dom.versionList) return;
      var snapshots = await this.listSnapshots();
      var self = this;

      if (snapshots.length === 0) {
        this.dom.versionList.innerHTML = '<p class="small muted">No snapshots yet.</p>';
        return;
      }

      this.dom.versionList.innerHTML = snapshots.map(function (s) {
        var date = new Date(s.created_at * 1000).toLocaleString();
        return (
          '<div class="collab-snapshot" data-id="' + s.id + '">' +
            '<div class="snapshot-header">' +
              '<span class="snapshot-label">' + self._escape(s.label) + "</span>" +
              '<span class="snapshot-time">' + date + "</span>" +
            "</div>" +
            '<div class="snapshot-meta">' + s.content_length + " chars" +
            '<div class="snapshot-actions">' +
              '<button class="snapshot-rollback-btn" data-id="' + s.id + '">Rollback</button>' +
            "</div>" +
          "</div>"
        );
      }).join("");

      this.dom.versionList.querySelectorAll(".snapshot-rollback-btn").forEach(function (btn) {
        btn.addEventListener("click", async function () {
          if (!confirm("Rollback to this snapshot? Current changes will be replaced.")) return;
          var result = await self.rollback(btn.dataset.id);
          if (result && result.snapshot && self.quill) {
            self.quill.setText(result.snapshot.content);
            self._setStatus("connected", "Rolled back to snapshot");
          }
        });
      });
    },

    _escape: function (text) {
      var div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    },
  };

  // Expose globally
  window.CollabEditor = CollabEditor;
})();
