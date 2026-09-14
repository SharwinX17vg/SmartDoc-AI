const API_BASE = `${window.SMARTDOC_API_ORIGIN}/api/v1`;
const state = { documents: [], selected: new Set(), history: [], busy: false, uploading: false, requestVersion: 0, controller: null };
const $ = (selector) => document.querySelector(selector);
const fileInput = $("#pdf-file");
const documentList = $("#document-list");
const documentCount = $("#document-count");
const studyAllButton = $("#study-all-button");
const clearButton = $("#clear-button");
const uploadStatus = $("#upload-status");
const scopeStatus = $("#scope-status");
const chat = $("#chat");
const question = $("#question");
const askButton = $("#ask-button");
const message = $("#message");

fileInput.addEventListener("change", uploadFiles);
askButton.addEventListener("click", askQuestion);
clearButton.addEventListener("click", clearWorkspace);
studyAllButton.addEventListener("click", () => { state.selected = new Set(state.documents.map((doc) => doc.document_id)); renderDocuments(); question.value = "Study all my documents and give me the important topics"; askQuestion(); });
question.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); askQuestion(); } });
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => { question.value = button.dataset.prompt; question.focus(); }));
loadDocuments();

async function uploadFiles() {
  if (!fileInput.files.length) return;
  if (state.busy || state.uploading) return setStatus("Please wait for the current request to finish.", true);
  state.uploading = true;
  const version = ++state.requestVersion;
  setStatus("Uploading and indexing documents...");
  const formData = new FormData();
  [...fileInput.files].forEach((file) => formData.append("files", file));
  try {
    const response = await fetch(`${API_BASE}/documents/batch`, { method: "POST", body: formData });
    const data = await readResponse(response);
    setStatus(data.failures.length ? `Indexed ${data.uploaded.length}; ${data.failures.length} failed.` : `Indexed ${data.uploaded.length} document(s).`);
    if (version === state.requestVersion) await loadDocuments();
  } catch (error) { setStatus(error.message, true); }
  finally { state.uploading = false; fileInput.value = ""; }
}

async function loadDocuments() {
  const version = state.requestVersion;
  try { const data = await readResponse(await fetch(`${API_BASE}/documents`)); if (version !== state.requestVersion) return; state.documents = data.documents; state.selected = new Set(state.documents.map((doc) => doc.document_id)); renderDocuments(); }
  catch (error) { setStatus("SmartDoc could not connect to the backend.", true); }
}

function renderDocuments() {
  documentCount.textContent = `${state.documents.length} document${state.documents.length === 1 ? "" : "s"}`;
  documentList.replaceChildren();
  if (!state.documents.length) { const empty = document.createElement("p"); empty.className = "empty-state"; empty.textContent = "Upload one or more PDFs to start."; documentList.append(empty); }
  state.documents.forEach((doc) => {
    const row = document.createElement("div"); row.className = "document-row";
    const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.checked = state.selected.has(doc.document_id); checkbox.addEventListener("change", () => { checkbox.checked ? state.selected.add(doc.document_id) : state.selected.delete(doc.document_id); renderScope(); });
    const name = document.createElement("span"); name.className = "document-name"; name.textContent = doc.document_name; name.title = doc.document_name;
    const meta = document.createElement("span"); meta.className = "document-meta"; meta.textContent = `${doc.page_count}p`;
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "icon-button"; remove.textContent = "Remove"; remove.title = `Remove ${doc.document_name}`; remove.addEventListener("click", () => removeDocument(doc.document_id));
    row.append(checkbox, name, meta, remove); documentList.append(row);
  });
  studyAllButton.disabled = !state.documents.length; renderScope();
}

async function removeDocument(documentId) {
  state.requestVersion++;
  state.controller?.abort();
  try { await readResponse(await fetch(`${API_BASE}/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" })); await loadDocuments(); setStatus("Document removed."); }
  catch (error) { setStatus(error.message, true); }
}

function renderScope() { scopeStatus.textContent = state.selected.size ? `Using ${state.selected.size} document${state.selected.size === 1 ? "" : "s"}` : "Select documents"; }

async function clearWorkspace() {
  if (!state.documents.length) return;
  state.requestVersion++;
  state.controller?.abort();
  try { await readResponse(await fetch(`${API_BASE}/documents/clear`, { method: "POST" })); state.documents = []; state.selected.clear(); state.history = []; chat.replaceChildren(); renderDocuments(); setStatus("Workspace cleared."); }
  catch (error) { setStatus(error.message, true); }
}

async function askQuestion() {
  const text = question.value.trim();
  if (!text) return;
  if (state.busy) return;
  if (!state.selected.size && !isCasual(text)) return setStatus("Select at least one document first.", true);
  question.value = ""; appendMessage("user", text); setBusy(true); setStatus("Searching documents...");
  const version = ++state.requestVersion;
  state.controller = new AbortController();
  try {
    const response = await readResponse(await fetch(`${API_BASE}/query`, { method: "POST", signal: state.controller.signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: text, top_k: 5, selected_document_ids: [...state.selected], conversation: state.history.slice(-8) }) }));
    if (version !== state.requestVersion) return;
    state.history.push({ role: "user", content: text }, { role: "assistant", content: response.answer });
    appendMessage("assistant", response.answer, response.sources);
    setStatus("");
  } catch (error) { if (error.name !== "AbortError" && version === state.requestVersion) { appendMessage("assistant", error.message); setStatus("Request failed.", true); } }
  finally { setBusy(false); }
}

function appendMessage(role, text, sourceItems = []) {
  const row = document.createElement("article"); row.className = `message-row ${role}`;
  const bubble = document.createElement("div"); bubble.className = "bubble answer-markdown"; renderText(bubble, text); row.append(bubble);
  if (role === "assistant") {
    if (sourceItems.length) { const list = document.createElement("div"); list.className = "source-list"; sourceItems.forEach((source) => { const card = document.createElement("div"); card.className = "source-card"; card.textContent = `${source.document_name} · Page ${source.page_number}`; const detail = document.createElement("small"); detail.textContent = source.section_title || "Retrieved source"; card.append(detail); list.append(card); }); row.append(list); }
    const tools = document.createElement("div"); tools.className = "message-tools"; tools.append(toolButton("Copy", () => copyText(text)), toolButton("Share", () => shareAnswer(text, sourceItems)), toolButton("Download", () => downloadText(text))); row.append(tools);
  }
  chat.append(row); chat.scrollTop = chat.scrollHeight;
}

function renderText(container, text) {
  const lines = String(text).split(/\n/); let list = null;
  lines.forEach((line) => { const trimmed = line.trim(); if (!trimmed) { list = null; return; } const bullet = trimmed.match(/^[-•]\s+(.+)/); if (bullet) { if (!list) { list = document.createElement("ul"); container.append(list); } const item = document.createElement("li"); item.textContent = bullet[1]; list.append(item); return; } list = null; const paragraph = document.createElement("p"); paragraph.textContent = trimmed; container.append(paragraph); });
}
function toolButton(label, handler) { const button = document.createElement("button"); button.type = "button"; button.textContent = label; button.addEventListener("click", handler); return button; }
async function copyText(text) { try { await navigator.clipboard.writeText(text); setStatus("Copied ✓"); } catch { const area = document.createElement("textarea"); area.value = text; document.body.append(area); area.select(); document.execCommand("copy"); area.remove(); setStatus("Copied ✓"); } }
async function shareAnswer(text, sourceItems) { try { const data = await readResponse(await fetch(`${API_BASE}/share`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer: text, sources: sourceItems }) })); if (navigator.share) await navigator.share({ title: "SmartDoc AI answer", text, url: data.share_url }); else await copyText(data.share_url); } catch (error) { setStatus(error.message, true); } }
function downloadText(text) { const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([text], { type: "text/plain" })); link.download = "smartdoc-answer.txt"; link.click(); URL.revokeObjectURL(link.href); }
async function readResponse(response) { const data = await response.json(); if (!response.ok) throw new Error(data.detail || "SmartDoc could not complete that request."); return data; }
function isCasual(text) { return /^(h+i+|hello|hey|good morning|good afternoon|good evening|how are you|what's up|thanks|thank you|thanks a lot|okay thanks|ok thanks|bye|goodbye|see you|see ya)[!. ]*$/i.test(text.trim()); }
function setBusy(busy) { state.busy = busy; askButton.disabled = busy; askButton.textContent = busy ? "..." : "Send"; }
function setStatus(text, error = false) { uploadStatus.textContent = text; message.textContent = text; message.className = error ? "message error" : "message"; }
