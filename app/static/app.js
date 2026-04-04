// DOM elements
const form = document.querySelector("#chat-form");
const input = document.querySelector("#chat-input");
const messages = document.querySelector("#messages");
const uploadBtn = document.querySelector("#upload-btn");
const fileInput = document.querySelector("#file-input");
const documentsList = document.querySelector("#documents-list");
const clearBtn = document.querySelector("#clear-chat");

// Utility: Add message to chat
function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

// Send query to backend and get response
async function sendMessage(text) {
  if (!text.trim()) return;

  addMessage("user", text);

  const botMsg = document.createElement("div");
  botMsg.className = "message assistant";
  botMsg.textContent = "Thinking...";
  messages.appendChild(botMsg);

  try {
    const response = await fetch("/api/v1/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        question: text,
        session_id: "web-session",
        document_ids: [],
        history: []
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (data.answer) {
      botMsg.textContent = data.answer;
      if (data.citations && data.citations.length > 0) {
        const citationsText = "\n\n📚 Sources:\n" + data.citations.map(c => `• ${c.document_id}`).join("\n");
        botMsg.textContent += citationsText;
      }
    } else if (data.message) {
      botMsg.textContent = `⚠️ ${data.message}`;
    } else {
      botMsg.textContent = "No answer generated. Check that documents are uploaded.";
    }

  } catch (error) {
    console.error("Query failed:", error);
    botMsg.textContent = `❌ Error: ${error.message}`;
  }
}

// Form submission handler
if (form && input) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.disabled = true;

    try {
      await sendMessage(text);
    } finally {
      input.disabled = false;
      input.focus();
    }
  });
}

// Upload handler
if (uploadBtn && fileInput) {
  uploadBtn.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", async (e) => {
    const files = e.target.files;
    if (files.length === 0) return;

    uploadBtn.disabled = true;
    uploadBtn.textContent = "Uploading...";

    try {
      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file);
      }

      const response = await fetch("/api/v1/upload", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`);
      }

      const data = await response.json();
      addMessage("system", `✅ Uploaded ${data.document_ids?.length || 0} document(s)`);
      fileInput.value = "";
      loadDocuments();

    } catch (error) {
      console.error("Upload error:", error);
      addMessage("system", `❌ Upload failed: ${error.message}`);
    } finally {
      uploadBtn.disabled = false;
      uploadBtn.textContent = "Upload PDF";
    }
  });
}

// Load documents list
async function loadDocuments() {
  if (!documentsList) return;

  try {
    const response = await fetch("/api/v1/documents");
    const data = await response.json();

    documentsList.innerHTML = "<h3>Docs</h3>";
    if (data.documents && data.documents.length > 0) {
      data.documents.forEach(doc => {
        const docEl = document.createElement("div");
        docEl.style.fontSize = "0.85em";
        docEl.style.padding = "5px";
        docEl.style.marginBottom = "3px";
        docEl.style.opacity = "0.8";
        docEl.textContent = `📄 ${doc.document_id} (${doc.size_kb}KB)`;
        documentsList.appendChild(docEl);
      });
    } else {
      const emptyEl = document.createElement("div");
      emptyEl.style.fontSize = "0.85em";
      emptyEl.style.opacity = "0.5";
      emptyEl.textContent = "(No documents)";
      documentsList.appendChild(emptyEl);
    }
  } catch (error) {
    console.error("Failed to load documents:", error);
  }
}

// Clear chat handler
if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    if (messages) {
      messages.innerHTML = "";
    }
  });
}

// Initialize on load
document.addEventListener("DOMContentLoaded", () => {
  loadDocuments();
  if (input) input.focus();
});