// Single Source of Truth for API
const API_BASE_URL = window.location.origin + "/api/v1";

const drop = document.getElementById('drop-zone');
const fileIn = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const idxBtn = document.getElementById('index-btn');
const qIn = document.getElementById('q-in');
const sendBtn = document.getElementById('send-btn');
const chatFlow = document.getElementById('chat-area');
const empty = document.getElementById('empty');
const tstMsg = document.getElementById('toast-msg');
const tst = document.getElementById('toast');

let activeDocumentIds = [];
let isBusy = false;
let sessionHistory = [];

const showToast = (txt, isErr=false) => { 
    tstMsg.textContent = txt; 
    tst.className = `toast show ${isErr?'err':'ok'}`; 
    setTimeout(() => tst.className = 'toast hidden', 5000); 
};

// Robust Fetch Wrapper
async function apiFetch(endpoint, options = {}, retries = 1, timeoutMs = 20000) {
    for (let attempt = 0; attempt <= retries; attempt++) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, { ...options, signal: controller.signal });
            clearTimeout(timeoutId);
            
            let data;
            try { data = await response.json(); } catch(e) { data = null; }
            
            if(!response.ok) {
                const errMsg = data?.message || data?.detail || `HTTP ${response.status}`;
                throw new Error(errMsg);
            }
            return data;
        } catch (err) {
            clearTimeout(timeoutId);
            if (err.name === 'AbortError') {
                if (attempt === retries) throw new Error('Request timed out. Server might be busy.');
            } else if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
                if (attempt === retries) throw new Error('Backend offline. Check connection to API_BASE_URL.');
            } else {
                // If it's a generated 4xx or 5xx structured error, return directly without retrying
                throw err; 
            }
            await new Promise(r => setTimeout(r, 1000 * (attempt + 1))); // Backoff
        }
    }
}

// Health Check
async function health() {
    try {
        await apiFetch('/health', {}, 0, 3000);
        document.getElementById('stat-dot').className = 'dot ok';
        document.getElementById('stat-txt').textContent = 'Backend Online';
        document.getElementById('stat-dot-left').className = 'dot ok';
        document.getElementById('stat-txt-left').textContent = 'Online';
        qIn.disabled = false;
    } catch (e) {
        document.getElementById('stat-dot').className = 'dot err';
        document.getElementById('stat-txt').textContent = 'Backend Offline';
        document.getElementById('stat-dot-left').className = 'dot err';
        document.getElementById('stat-txt-left').textContent = 'Offline';
        qIn.disabled = true;
    }
}
setInterval(health, 8000); health();

// Upload Logic
drop.onclick = (e) => e.target!==idxBtn && fileIn.click();
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('drag'); };
drop.ondragleave = () => drop.classList.remove('drag');
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('drag'); procFiles(e.dataTransfer.files); };
fileIn.onchange = (e) => procFiles(e.target.files);

function procFiles(flist) {
    const files = Array.from(flist).filter(f=>f.name.toLowerCase().endsWith('.pdf'));
    if(!files.length) return showToast('Please upload PDF files only', true);
    idxBtn.style.display = 'block';
    idxBtn.classList.add('animate-pop');
    
    // Store files globally for upload click
    window._pendingFiles = files;
    
    fileList.innerHTML = files.map(f=>`
        <div class="file-item animate-fade">
            <div class="file-item-top"><span>${f.name}</span><span style="color:var(--text-sec)">Queued</span></div>
        </div>
    `).join('');
}

idxBtn.onclick = async () => {
    if(!window._pendingFiles || !window._pendingFiles.length) return;
    idxBtn.disabled = true; idxBtn.innerHTML = 'Uploading...';
    
    const fd = new FormData(); 
    window._pendingFiles.forEach(f => fd.append('files', f));
    
    try {
        const d = await apiFetch('/upload', { method:'POST', body:fd }, 0, 40000);
        showToast(d.message || "Upload successful");
        
        // Append IDs mapping
        activeDocumentIds.push(...d.document_ids);
        document.getElementById('stat-docs').textContent = activeDocumentIds.length;
        
        fileList.innerHTML = window._pendingFiles.map((f, i) => `
            <div class="file-item">
                <div class="file-item-top"><span>${f.name}</span><span style="color:var(--c-info)">Ready</span></div>
                <div class="file-item-id">ID: ${d.document_ids[i]}</div>
            </div>
        `).join('');
        
        window._pendingFiles = []; 
        setTimeout(() => idxBtn.style.display='none', 2000);
    } catch(e) { 
        showToast(e.message, true); 
        fileList.innerHTML = window._pendingFiles.map(f => `
            <div class="file-item">
                <div class="file-item-top"><span>${f.name}</span><span style="color:var(--c-err)">Failed</span></div>
            </div>
        `).join('');
    } finally { 
        idxBtn.disabled = false; idxBtn.innerHTML = 'Upload & Index'; fileIn.value = ''; 
    }
};

// Chat
qIn.oninput = function() { 
    this.style.height = 'auto'; this.style.height = this.scrollHeight + 'px'; 
    sendBtn.disabled = !this.value.trim(); 
};
qIn.onkeydown = (e) => { 
    if(e.key === 'Enter' && !e.shiftKey) { 
        e.preventDefault(); 
        if(!sendBtn.disabled && !isBusy) sendQ(); 
    } 
};
sendBtn.onclick = () => { if(!sendBtn.disabled && !isBusy) sendQ(); };

const scrollChat = () => chatFlow.scrollTop = chatFlow.scrollHeight;

function addMessage(role, txt) {
    empty.style.display = 'none';
    const d = document.createElement('div'); d.className = `msg ${role} animate-fade`;
    const rn = role === 'user' ? 'You' : 'DocuMind Base';
    d.innerHTML = `<div class="msg-info"><span>${rn}</span></div><div class="msg-bubble">${txt.replace(/\\n/g,'<br>')}</div>`;
    chatFlow.appendChild(d); scrollChat(); 
    
    sessionHistory.push({ role, content: txt });
    renderHistory();
    return d;
}

function typeWriter(element, text, cb) {
    let i = 0;
    element.innerHTML = '<span class="typewriter-cursor"></span>';
    const interval = setInterval(() => {
        const char = text.charAt(i) === '\\n' ? '<br>' : text.charAt(i);
        element.innerHTML = element.innerHTML.replace('<span class="typewriter-cursor"></span>', '') + char + '<span class="typewriter-cursor"></span>';
        i++;
        scrollChat();
        if(i >= text.length) {
            clearInterval(interval);
            element.innerHTML = element.innerHTML.replace('<span class="typewriter-cursor"></span>', '');
            if(cb) cb();
        }
    }, 8); // Speedy delivery
}

function createErrorCard(title, msg, suggestion) {
    const d = document.createElement('div');
    d.className = 'msg bot animate-fade'; d.style.maxWidth = '100%';
    d.innerHTML = `<div class="msg-info"><span>System</span></div>
        <div class="error-card">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <div>
                <div class="error-title">${title}</div>
                <div class="error-desc">${msg}</div>
                <div class="error-desc" style="margin-top:4px; font-weight: 500;">Tip: ${suggestion}</div>
            </div>
        </div>`;
    return d;
}

async function sendQ() {
    const q = qIn.value.trim(); if(!q) return;
    isBusy = true; qIn.value = ''; qIn.style.height = 'auto'; 
    sendBtn.disabled = true; qIn.disabled = true;
    
    addMessage('user', q);
    
    const skel = document.createElement('div'); skel.className = 'msg bot animate-fade';
    skel.innerHTML = `<div class="msg-info"><span>DocuMind Base</span></div><div class="skeleton-block"><div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div></div>`;
    chatFlow.appendChild(skel); scrollChat();

    try {
        const payload = {
            question: q,
            session_id: "default",
            document_ids: activeDocumentIds
        };
        
        const d = await apiFetch('/query', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(payload)
        });
        
        chatFlow.removeChild(skel);
        
        if (d.status === "error") {
            chatFlow.appendChild(createErrorCard("Retrieval Error", d.message || "An error occurred", "Have you uploaded any PDFs yet?"));
            return;
        }
        
        const div = document.createElement('div'); div.className='msg bot animate-fade';
        let html = `<div class="msg-info"><span>DocuMind Base</span></div>`;
        html += `<div class="msg-bubble" id="ans-typing"></div>`;
        
        div.innerHTML = html;
        chatFlow.appendChild(div);

        let citesHtml = '';
        if(d.citations && d.citations.length) {
            const chips = d.citations.map(c => `
                <div class="cite-chip" title="Page ${c.page}: ${c.snippet.replace(/"/g,'&quot;')}">
                    Page ${c.page}
                </div>
            `).join('');
            citesHtml = `<div class="citations animate-fade"><span style="font-size: 11px; margin-right: 8px; font-weight: 600; color: var(--text-sec)">Source:</span> ${chips}</div>`;
        }
        
        const ans = d.answer || "No answer provided.";
        typeWriter(document.getElementById(`ans-typing`), ans, () => {
            document.getElementById(`ans-typing`).removeAttribute('id'); // cleanup id
            if(citesHtml) {
                const extras = document.createElement('div');
                extras.innerHTML = citesHtml;
                div.appendChild(extras);
                scrollChat();
            }
            qIn.disabled = false; qIn.focus();
            
            sessionHistory.push({ role: 'bot', content: ans });
            renderHistory();
        });

    } catch(e) {
        if(chatFlow.contains(skel)) chatFlow.removeChild(skel);
        chatFlow.appendChild(createErrorCard('Network/System Error', e.message, 'Check backend console via uvicorn.'));
        console.error(e);
        qIn.disabled = false;
    } finally { 
        isBusy = false; 
    }
}

// History
function renderHistory() {
    const list = document.getElementById('hist-list');
    if(sessionHistory.length === 0) {
        list.innerHTML = `<div class="text-sm text-sec" style="text-align:center; padding-top:2rem;">No conversation history.</div>`;
        return;
    }
    
    // Reverse display and limit to last 20
    const reversed = [...sessionHistory].reverse().slice(0, 20);
    list.innerHTML = reversed.map(m => `
        <div class="hist-item animate-fade">
            <div class="hist-role ${m.role==='user'?'you':''}">${m.role==='user'?'You':'DocuMind'}</div>
            <div class="hist-text">${m.content}</div>
        </div>
    `).join('');
}

document.getElementById('clear-btn').onclick = () => {
    if(!confirm('Clear conversation history locally?')) return;
    sessionHistory = [];
    chatFlow.innerHTML = ''; 
    chatFlow.appendChild(empty); 
    empty.style.display = 'flex';
    renderHistory();
};
