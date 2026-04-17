const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const templateSelect = document.getElementById("templateSelect");
const sessionInfoEl = document.getElementById("sessionInfo");
const insightBoxEl = document.getElementById("insightBox");
const newSessionBtn = document.getElementById("newSessionBtn");

let sessionId = null;

function appendMessage(role, text, options = {}) {
  const node = document.createElement("article");
  node.className = `message ${role}`;

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = role === "user" ? "You" : "Research Agent";
  node.appendChild(meta);

  const content = document.createElement("div");
  content.textContent = text;
  node.appendChild(content);

  if (options.links) {
    const links = document.createElement("div");
    links.className = "links";
    Object.entries(options.links).forEach(([label, href]) => {
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = label;
      links.appendChild(link);
    });
    node.appendChild(links);
  }

  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function ensureSession() {
  if (sessionId) {
    return sessionId;
  }

  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template: templateSelect.value }),
  });

  if (!response.ok) {
    throw new Error("Failed to create session.");
  }

  const payload = await response.json();
  sessionId = payload.session_id;
  sessionInfoEl.textContent = `Session: ${sessionId}`;
  return sessionId;
}

function renderInsights(payload) {
  if (payload.kind !== "result") {
    insightBoxEl.textContent = "Clarification phase active.";
    return;
  }

  const confidence = Object.entries(payload.section_confidence || {})
    .map(([k, v]) => `${k}: ${v.toFixed(2)}`)
    .join("\n");

  const notes = (payload.critic_notes || []).map((x) => `- ${x}`).join("\n") || "- none";
  const warnings = (payload.warnings || []).slice(0, 6).map((x) => `- ${x}`).join("\n") || "- none";

  insightBoxEl.textContent = [
    `Run: ${payload.run_id || "n/a"}`,
    "",
    "Confidence:",
    confidence || "n/a",
    "",
    "Critic:",
    notes,
    "",
    "Warnings:",
    warnings,
  ].join("\n");
}

async function sendMessage(text) {
  const sid = await ensureSession();

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sid,
      message: text,
      template: templateSelect.value,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Request failed");
  }

  return response.json();
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  messageInput.value = "";

  try {
    const payload = await sendMessage(text);

    if (payload.kind === "clarification") {
      const questionText = [payload.assistant_message, "", ...(payload.questions || []).map((q, i) => `${i + 1}. ${q}`)].join("\n");
      appendMessage("assistant", questionText);
      messageInput.placeholder = "Answer the clarification questions to continue...";
    } else {
      appendMessage("assistant", payload.assistant_message, {
        links: {
          "main.tex": payload.artifact_urls?.main_tex,
          "references.bib": payload.artifact_urls?.references_bib,
          "compile instructions": payload.artifact_urls?.compile_instructions,
          "summary.json": payload.artifact_urls?.summary,
        },
      });
      messageInput.placeholder = "Enter a new research topic...";
    }

    renderInsights(payload);
  } catch (error) {
    appendMessage("assistant", `Error: ${error.message}`);
  }
});

newSessionBtn.addEventListener("click", () => {
  sessionId = null;
  sessionInfoEl.textContent = "Session: not initialized";
  insightBoxEl.textContent = "No run yet.";
  appendMessage("assistant", "Started a fresh session. You can send a new topic.");
});

appendMessage("assistant", "Welcome. Enter a research topic to begin.");
