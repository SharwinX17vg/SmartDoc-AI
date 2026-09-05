const API_BASE = `${window.SMARTDOC_API_ORIGIN}/api/v1`;

const fileInput = document.querySelector("#pdf-file");
const fileName = document.querySelector("#file-name");
const uploadButton = document.querySelector("#upload-button");
const askButton = document.querySelector("#ask-button");
const questionInput = document.querySelector("#question");
const message = document.querySelector("#message");
const answerPanel = document.querySelector("#answer-panel");
const answer = document.querySelector("#answer");
const sources = document.querySelector("#sources");
const documentStatus = document.querySelector("#document-status");

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0]?.name || "No file selected";
});

uploadButton.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return setMessage("Choose a PDF first.", true);
  setBusy(uploadButton, "Uploading...");
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/documents`, { method: "POST", body: formData });
    const data = await readResponse(response);
    documentStatus.textContent = `${data.page_count} pages indexed`;
    askButton.disabled = false;
    setMessage(`${data.document_name} is ready for questions.`);
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    setBusy(uploadButton, "Upload document");
  }
});

askButton.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) return setMessage("Enter a question or command.", true);
  setBusy(askButton, "Retrieving...");
  try {
    const response = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 5 }),
    });
    const data = await readResponse(response);
    answer.textContent = data.answer;
    sources.replaceChildren(...data.sources.map(renderSource));
    answerPanel.hidden = false;
    setMessage("");
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    setBusy(askButton, "Ask SmartDoc");
  }
});

async function readResponse(response) {
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "The backend request failed.");
  return data;
}

function renderSource(source) {
  const item = document.createElement("article");
  item.className = "source";
  item.innerHTML = `<strong>${escapeHtml(source.document_name)} · page ${source.page_number}</strong><p>${escapeHtml(source.chunk_text)}</p>`;
  return item;
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[character]));
}

function setBusy(button, label) {
  button.disabled = label.endsWith("...");
  button.textContent = label;
}

function setMessage(text, isError = false) {
  message.textContent = text;
  message.style.color = isError ? "#9a3f32" : "";
}
