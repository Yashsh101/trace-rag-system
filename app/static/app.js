const API = {
  documents: "/api/v1/documents",
  queryStream: "/api/v1/query/stream"
};

const state = {
  documents: [],
  streaming: false
};

const els = {
  body: document.body,
  dropzone: document.querySelector("#dropzone"),
  fileInput: document.querySelector("#file-input"),
  uploadProgress: document.querySelector("#upload-progress"),
  uploadStatus: document.querySelector("#upload-status"),
  documentList: document.querySelector("#document-list"),
  documentCount: document.querySelector("#document-count"),
  chatFeed: document.querySelector("#chat-feed"),
  emptyState: document.querySelector("#empty-state"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  sendButton: document.querySelector("#send-button"),
  statusBadge: document.querySelector(".status-badge"),
  statusLabel: document.querySelector("#status-label"),
  toastRegion: document.querySelector("#toast-region")
};

document.addEventListener("DOMContentLoaded", init);

function init() {
  bindEvents();
  loadDocuments();
}

function bindEvents() {
  els.chatForm.addEventListener("submit", event => {
    event.preventDefault();
    submitQuestion();
  });

  els.chatInput.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitQuestion();
    }
  });

  els.fileInput.addEventListener("change", event => {
    uploadFiles([...event.target.files]);
    els.fileInput.value = "";
  });

  ["dragenter", "dragover"].forEach(type => {
    els.dropzone.addEventListener(type, event => {
      event.preventDefault();
      els.dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach(type => {
    els.dropzone.addEventListener(type, event => {
      event.preventDefault();
      els.dropzone.classList.remove("is-dragover");
    });
  });

  els.dropzone.addEventListener("drop", event => {
    uploadFiles([...event.dataTransfer.files]);
  });
}

async function loadDocuments() {
  setStatus("Loading", true);
  try {
    const payload = await requestJson(API.documents);
    state.documents = normalizeDocuments(payload);
    renderDocuments();
    setStatus("Ready", false);
  } catch (error) {
    renderDocuments();
    setStatus("Ready", false);
    toast(error.message || "Could not load documents", "error");
  }
}

function renderDocuments() {
  els.documentCount.textContent = String(state.documents.length);
  els.documentList.innerHTML = "";

  if (!state.documents.length) {
    const empty = document.createElement("div");
    empty.className = "empty-list";
    empty.textContent = "No indexed documents yet. Upload PDFs to start asking grounded questions.";
    els.documentList.appendChild(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  state.documents.forEach(doc => {
    const card = document.createElement("article");
    card.className = "document-card";
    card.innerHTML = `
      <div>
        <div class="document-name" title="${escapeHtml(doc.name)}">${escapeHtml(doc.name)}</div>
        <div class="document-meta">
          <span class="doc-badge">${escapeHtml(doc.sizeLabel)}</span>
          <span class="doc-badge">${escapeHtml(doc.pagesLabel)}</span>
        </div>
      </div>
      <button class="delete-button" type="button" title="Delete document" aria-label="Delete ${escapeHtml(doc.name)}">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
          <path d="M4 7h16M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    `;
    card.querySelector(".delete-button").addEventListener("click", () => deleteDocument(doc.id));
    fragment.appendChild(card);
  });
  els.documentList.appendChild(fragment);
}

async function uploadFiles(files) {
  const pdfs = files.filter(file => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"));
  if (!pdfs.length) {
    toast("Select a PDF file to upload.", "error");
    return;
  }

  for (const file of pdfs) {
    await uploadFile(file);
  }
  await loadDocuments();
}

function uploadFile(file) {
  return new Promise(resolve => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);

    setUploadProgress(4, `Uploading ${file.name}`);
    setStatus("Uploading", true);

    xhr.open("POST", API.documents);
    addAuthHeader(xhr);

    xhr.upload.addEventListener("progress", event => {
      if (!event.lengthComputable) return;
      const progress = Math.max(8, Math.round((event.loaded / event.total) * 92));
      setUploadProgress(progress, `Uploading ${file.name}`);
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        setUploadProgress(100, "Upload complete");
        toast(`${file.name} uploaded`);
      } else {
        toast(readXhrError(xhr) || `Upload failed for ${file.name}`, "error");
      }
      setStatus("Ready", false);
      setTimeout(() => setUploadProgress(0, "Idle"), 700);
      resolve();
    });

    xhr.addEventListener("error", () => {
      toast(`Upload failed for ${file.name}`, "error");
      setStatus("Ready", false);
      setUploadProgress(0, "Idle");
      resolve();
    });

    xhr.send(form);
  });
}

async function deleteDocument(id) {
  if (!id) return;
  try {
    await requestJson(`${API.documents}/${encodeURIComponent(id)}`, { method: "DELETE" });
    state.documents = state.documents.filter(doc => String(doc.id) !== String(id));
    renderDocuments();
    toast("Document deleted");
  } catch (error) {
    toast(error.message || "Delete failed", "error");
  }
}

async function submitQuestion() {
  const question = els.chatInput.value.trim();
  if (!question || state.streaming) return;

  state.streaming = true;
  els.chatInput.value = "";
  setComposerDisabled(true);
  setStatus("Streaming", true);
  removeEmptyState();

  addMessage("user", question);
  const aiMessage = addMessage("assistant", "", { streaming: true });

  try {
    await streamQuery(question, aiMessage);
  } catch (error) {
    updateMessage(aiMessage, "I could not complete the request. Check the API connection and try again.");
    toast(error.message || "Query failed", "error");
  } finally {
    aiMessage.cursor?.remove();
    state.streaming = false;
    setComposerDisabled(false);
    setStatus("Ready", false);
    els.chatInput.focus();
  }
}

async function streamQuery(question, aiMessage) {
  const response = await fetch(API.queryStream, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders()
    },
    body: JSON.stringify({ question })
  });

  if (!response.ok) {
    throw new Error(await readFetchError(response));
  }

  const contentType = response.headers.get("content-type") || "";
  if (!response.body || !contentType.includes("text/event-stream")) {
    const payload = await response.json();
    const answer = payload.answer || payload.text || "";
    updateMessage(aiMessage, answer);
    renderCitations(aiMessage, payload.citations || payload.sources || []);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  let citations = [];

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";

    for (const frame of frames) {
      const event = parseSseFrame(frame);
      if (!event) continue;

      if (event.type === "citation" || event.type === "citations" || event.data?.citations) {
        citations = event.data?.citations || event.data || citations;
        continue;
      }

      if (event.type === "done") {
        if (event.data?.answer) answer = event.data.answer;
        if (event.data?.citations) citations = event.data.citations;
        continue;
      }

      const token = event.data?.token ?? event.data?.text ?? event.data?.delta ?? (typeof event.data === "string" ? event.data : "");
      if (token) {
        answer += token;
        updateMessage(aiMessage, answer);
        await nextFrame();
      }
    }
  }

  updateMessage(aiMessage, answer || "No answer returned.");
  renderCitations(aiMessage, citations);
}

function addMessage(role, text, options = {}) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const message = document.createElement("article");
  message.className = "message";

  const shell = document.createElement("div");
  shell.className = "message-shell";

  const content = document.createElement("div");
  content.className = "message-content";
  content.innerHTML = renderMarkdown(text);

  const copy = document.createElement("button");
  copy.className = "copy-button";
  copy.type = "button";
  copy.title = "Copy message";
  copy.setAttribute("aria-label", "Copy message");
  copy.innerHTML = `
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
      <path d="M8 8V5.5A1.5 1.5 0 0 1 9.5 4h8A1.5 1.5 0 0 1 19 5.5v8A1.5 1.5 0 0 1 17.5 15H15M5.5 9h8A1.5 1.5 0 0 1 15 10.5v8a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 4 18.5v-8A1.5 1.5 0 0 1 5.5 9Z" stroke="currentColor" stroke-width="1.7"/>
    </svg>
  `;
  copy.addEventListener("click", () => copyText(message.dataset.rawText || text || ""));

  shell.append(content, copy);
  message.appendChild(shell);

  if (options.streaming) {
    const cursor = document.createElement("span");
    cursor.className = "streaming-cursor";
    content.appendChild(cursor);
    message.cursor = cursor;
  }

  message.content = content;
  message.dataset.rawText = text || "";
  row.appendChild(message);
  els.chatFeed.appendChild(row);
  scrollChat();
  return message;
}

function updateMessage(message, text) {
  message.dataset.rawText = text;
  message.content.innerHTML = renderMarkdown(text);
  if (state.streaming && message.cursor?.isConnected !== true) {
    message.content.appendChild(message.cursor);
  }
  scrollChat();
}

function renderCitations(message, citations) {
  const normalized = normalizeCitations(citations);
  if (!normalized.length) return;

  const existing = message.querySelector(".citation-list");
  existing?.remove();

  const list = document.createElement("div");
  list.className = "citation-list";
  normalized.forEach(citation => {
    const chip = document.createElement("span");
    chip.className = "citation-chip";
    chip.title = citation.snippet || "";
    chip.textContent = citation.label;
    list.appendChild(chip);
  });
  message.appendChild(list);
  scrollChat();
}

function normalizeDocuments(payload) {
  const items = Array.isArray(payload) ? payload : payload.documents || payload.items || payload.data || [];
  return items.map((item, index) => {
    const id = item.id ?? item.document_id ?? item.documentId ?? item.uuid ?? index;
    const name = item.filename || item.name || item.title || `Document ${index + 1}`;
    const size = item.size_bytes ?? item.sizeBytes ?? item.file_size ?? item.fileSize ?? item.bytes ?? 0;
    const pages = item.page_count ?? item.pageCount ?? item.pages ?? item.num_pages ?? null;
    return {
      id,
      name,
      sizeLabel: size ? formatBytes(Number(size)) : "Size unknown",
      pagesLabel: pages ? `${pages} page${Number(pages) === 1 ? "" : "s"}` : "Pages unknown"
    };
  });
}

function normalizeCitations(citations) {
  if (!Array.isArray(citations)) return [];
  return citations.map((citation, index) => {
    const pageStart = citation.page_start ?? citation.pageStart ?? citation.page ?? null;
    const pageEnd = citation.page_end ?? citation.pageEnd ?? pageStart;
    const filename = citation.filename || citation.source_filename || citation.source || `Source ${index + 1}`;
    const pageLabel = pageStart ? `p. ${pageStart}${pageEnd && pageEnd !== pageStart ? `-${pageEnd}` : ""}` : "source";
    return {
      label: `${filename} · ${pageLabel}`,
      snippet: citation.snippet || citation.text || ""
    };
  });
}

function parseSseFrame(frame) {
  const lines = frame.split(/\r?\n/);
  const type = lines.find(line => line.startsWith("event:"))?.slice(6).trim() || "message";
  const dataText = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).trim()).join("\n");
  if (!dataText) return null;
  try {
    return { type, data: JSON.parse(dataText) };
  } catch {
    return { type, data: dataText };
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers || {})
    }
  });
  if (!response.ok) {
    throw new Error(await readFetchError(response));
  }
  const text = await response.text();
  return text ? JSON.parse(text) : {};
}

function authHeaders() {
  const apiKey = localStorage.getItem("documind_api_key") || "";
  return apiKey ? { "X-API-Key": apiKey } : {};
}

function addAuthHeader(xhr) {
  const apiKey = localStorage.getItem("documind_api_key") || "";
  if (apiKey) xhr.setRequestHeader("X-API-Key", apiKey);
}

async function readFetchError(response) {
  const text = await response.text();
  if (!text) return `Request failed with HTTP ${response.status}`;
  try {
    const payload = JSON.parse(text);
    return payload?.error?.message || payload?.detail || `Request failed with HTTP ${response.status}`;
  } catch {
    return text;
  }
}

function readXhrError(xhr) {
  try {
    const payload = JSON.parse(xhr.responseText);
    return payload?.error?.message || payload?.detail || "";
  } catch {
    return xhr.responseText;
  }
}

function renderMarkdown(text) {
  if (!text) return "";
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return html.split(/\n{2,}/).map(block => `<p>${block.replace(/\n/g, "<br>")}</p>`).join("");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[char]);
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "Size unknown";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function setUploadProgress(value, label) {
  els.uploadProgress.style.width = `${Math.max(0, Math.min(100, value))}%`;
  els.uploadStatus.textContent = label;
}

function setComposerDisabled(disabled) {
  els.chatInput.disabled = disabled;
  els.sendButton.disabled = disabled;
}

function setStatus(label, busy) {
  els.statusLabel.textContent = label;
  els.statusBadge.classList.toggle("is-busy", Boolean(busy));
}

function removeEmptyState() {
  els.emptyState?.remove();
  els.emptyState = null;
}

function scrollChat() {
  els.chatFeed.scrollTop = els.chatFeed.scrollHeight;
}

function toast(message, type = "info") {
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.textContent = message;
  els.toastRegion.appendChild(node);
  setTimeout(() => node.remove(), 4200);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied");
  } catch {
    toast("Copy failed", "error");
  }
}

function nextFrame() {
  return new Promise(resolve => requestAnimationFrame(resolve));
}
