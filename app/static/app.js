const els = {
    form: document.querySelector("#chat-form"),
    input: document.querySelector("#chat-input"),
    messages: document.querySelector("#messages"),
    statusBadge: document.querySelector("#backend-status"),
    uploadInput: document.querySelector("#file-input"),
    uploadBtn: document.querySelector("#upload-btn"),
    docsList: document.querySelector("#documents-list"),
    clearBtn: document.querySelector("#clear-chat"),
};

let currentSessionId = "default";
let chatHistory = [];
let currentDocumentIds = [];

function setStatus(text, online = false) {
    if (!els.statusBadge) return;
    els.statusBadge.textContent = text;
    els.statusBadge.classList.remove("online", "offline");
    els.statusBadge.classList.add(online ? "online" : "offline");
}

async function checkBackendHealth() {
    try {
        const res = await fetch("/api/v1/health");
        if (!res.ok) throw new Error("Health check failed");
        const data = await res.json();

        if (data?.status === "ok") {
            setStatus("Backend online", true);
        } else {
            setStatus("Backend offline", false);
        }
    } catch (err) {
        setStatus("Backend offline", false);
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text ?? "";
    return div.innerHTML;
}

function addMessage(role, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = escapeHtml(text);

    wrapper.appendChild(bubble);
    els.messages.appendChild(wrapper);
    els.messages.scrollTop = els.messages.scrollHeight;

    return wrapper;
}

function updateMessage(wrapper, text) {
    if (!wrapper) return;
    const bubble = wrapper.querySelector(".bubble");
    if (bubble) {
        bubble.innerHTML = escapeHtml(text);
    }
    els.messages.scrollTop = els.messages.scrollHeight;
}

function addMeta(wrapper, citations = [], actions = []) {
    if (!wrapper) return;

    let meta = wrapper.querySelector(".meta-block");
    if (meta) meta.remove();

    meta = document.createElement("div");
    meta.className = "meta-block";

    if (citations.length) {
        const citationsEl = document.createElement("div");
        citationsEl.className = "citations";
        citations.forEach((c) => {
            const pill = document.createElement("div");
            pill.className = "citation-pill";
            pill.textContent = `${c.document_id || "Document"}${c.page ? ` • p.${c.page}` : ""}`;
            citationsEl.appendChild(pill);
        });
        meta.appendChild(citationsEl);
    }

    if (actions.length) {
        const actionsEl = document.createElement("div");
        actionsEl.className = "actions";
        actions.forEach((a) => {
            const label = a.label || a.title || a.text || "Action";
            const btn = document.createElement("button");
            btn.className = "action-chip";
            btn.type = "button";
            btn.dataset.action = label;
            btn.textContent = label;
            actionsEl.appendChild(btn);
        });
        meta.appendChild(actionsEl);
    }

    if (citations.length || actions.length) {
        wrapper.appendChild(meta);
    }
}

function parseSSEChunk(rawChunk) {
    const lines = rawChunk.split("\n");
    const dataLines = lines
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.replace(/^data:\s?/, ""));
    return dataLines.join("\n").trim();
}

async function sendMessage(question) {
    if (!question) return;

    addMessage("user", question);
    const assistantMsg = addMessage("assistant", "Thinking...");

    const payload = {
        question,
        document_ids: currentDocumentIds,
        history: chatHistory,
        session_id: currentSessionId,
    };

    let finalAnswer = "";
    let citations = [];
    let actions = [];

    try {
        const res = await fetch("/api/v1/chat/stream", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        if (!res.ok || !res.body) {
            throw new Error(`Request failed: ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";

            for (const part of parts) {
                const jsonText = parseSSEChunk(part);
                if (!jsonText) continue;

                try {
                    const chunk = JSON.parse(jsonText);

                    if (chunk.type === "token") {
                        finalAnswer += chunk.content || "";
                        updateMessage(assistantMsg, finalAnswer || "Thinking...");
                    } else if (chunk.type === "answer") {
                        finalAnswer = chunk.content || finalAnswer;
                        updateMessage(assistantMsg, finalAnswer || "Thinking...");
                    } else if (chunk.type === "citations") {
                        citations = chunk.content || [];
                    } else if (chunk.type === "actions") {
                        actions = chunk.content || [];
                    } else if (chunk.type === "error") {
                        throw new Error(chunk.content || "Unknown error");
                    }
                } catch (e) {
                    // ignore malformed chunk
                }
            }
        }

        if (!finalAnswer.trim()) {
            finalAnswer = "No response received.";
            updateMessage(assistantMsg, finalAnswer);
        }

        addMeta(assistantMsg, citations, actions);

        chatHistory.push({ role: "user", content: question });
        chatHistory.push({ role: "assistant", content: finalAnswer });
    } catch (err) {
        updateMessage(assistantMsg, `⚠️ Error: ${err.message}`);
    }
}

async function uploadFiles(files) {
    if (!files || files.length === 0) return;

    const formData = new FormData();
    for (const file of files) {
        formData.append("files", file);
    }

    try {
        const res = await fetch("/api/v1/upload", {
            method: "POST",
            body: formData,
        });

        if (!res.ok) {
            throw new Error(`Upload failed: ${res.status}`);
        }

        const data = await res.json();
        if (Array.isArray(data.document_ids)) {
            currentDocumentIds = data.document_ids;
        }

        await loadDocuments();
    } catch (err) {
        alert("Upload failed. Please try again.");
    }
}

function prettifyDocumentName(rawId) {
    if (!rawId) return "Untitled document";
    const cleaned = rawId.replace(/^[a-f0-9]{8,}_/i, "");
    return cleaned.replace(/_/g, " ");
}

async function loadDocuments() {
    try {
        const res = await fetch("/api/v1/documents");
        if (!res.ok) throw new Error("Could not load documents");

        const data = await res.json();
        const documents = Array.isArray(data.documents) ? data.documents : [];

        if (documents.length === 0) {
            els.docsList.innerHTML = `<div class="doc-empty">No documents uploaded yet.</div>`;
            return;
        }

        els.docsList.innerHTML = documents
            .map((doc) => {
                const rawId = doc.document_id || "Untitled";
                const label = prettifyDocumentName(rawId);
                return `<div class="doc-item" title="${escapeHtml(rawId)}">${escapeHtml(label)}</div>`;
            })
            .join("");
    } catch (err) {
        els.docsList.innerHTML = `<div class="doc-empty">Could not load documents.</div>`;
    }
}

function bindEvents() {
    if (els.form) {
        els.form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const question = els.input.value.trim();
            if (!question) return;
            els.input.value = "";
            await sendMessage(question);
        });
    }

    if (els.uploadBtn && els.uploadInput) {
        els.uploadBtn.addEventListener("click", () => els.uploadInput.click());

        els.uploadInput.addEventListener("change", async (e) => {
            const files = Array.from(e.target.files || []);
            await uploadFiles(files);
            els.uploadInput.value = "";
        });
    }

    if (els.clearBtn) {
        els.clearBtn.addEventListener("click", () => {
            chatHistory = [];
            els.messages.innerHTML = "";
        });
    }

    document.addEventListener("click", async (e) => {
        const chip = e.target.closest(".action-chip");
        if (!chip) return;
        const actionText = chip.dataset.action || chip.textContent.trim();
        if (!actionText) return;
        await sendMessage(actionText);
    });
}

async function init() {
    bindEvents();
    await checkBackendHealth();
    await loadDocuments();
    setInterval(checkBackendHealth, 10000);
}

init();