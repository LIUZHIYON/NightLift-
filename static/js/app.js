/**
 * Low-Light Enhancement — Frontend
 * One-click: upload → auto analyze → enhance → download
 */

const state = {
    file: null,
    taskId: null,
    pollTimer: null,
    isProcessing: false,
};

const $ = (sel) => document.querySelector(sel);

const dom = {
    uploadArea: $('#uploadArea'),
    fileInput: $('#fileInput'),
    selectBtn: $('#selectBtn'),
    filePreview: $('#filePreview'),
    fileIcon: $('#fileIcon'),
    fileName: $('#fileName'),
    fileSize: $('#fileSize'),
    changeBtn: $('#changeBtn'),
    processBtn: $('#processBtn'),
    analyzeSection: $('#analyzeSection'),
    analyzeGrid: $('#analyzeGrid'),
    progressSection: $('#progressSection'),
    progressFill: $('#progressFill'),
    progressText: $('#progressText'),
    resultSection: $('#resultSection'),
    resultContainer: $('#resultContainer'),
    downloadBtn: $('#downloadBtn'),
    newTaskBtn: $('#newTaskBtn'),
    errorSection: $('#errorSection'),
    errorMsg: $('#errorMsg'),
    retryBtn: $('#retryBtn'),
};

// ── file selection ──
dom.selectBtn.addEventListener('click', () => dom.fileInput.click());
dom.uploadArea.addEventListener('click', (e) => { if (e.target !== dom.selectBtn) dom.fileInput.click(); });
dom.fileInput.addEventListener('change', handleFileSelect);

dom.uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); dom.uploadArea.classList.add('drag-over'); });
dom.uploadArea.addEventListener('dragleave', () => dom.uploadArea.classList.remove('drag-over'));
dom.uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    dom.uploadArea.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) setFile(e.dataTransfer.files[0]);
});
dom.changeBtn.addEventListener('click', () => { dom.fileInput.value = ''; dom.fileInput.click(); });

function handleFileSelect(e) {
    if (e.target.files.length > 0) setFile(e.target.files[0]);
}

function setFile(file) {
    state.file = file;
    dom.fileName.textContent = file.name;
    dom.fileSize.textContent = formatSize(file.size);
    dom.fileIcon.textContent = file.type.startsWith('video/') ? 'V' : 'I';

    dom.uploadArea.classList.add('hidden');
    dom.filePreview.classList.remove('hidden');
    dom.processBtn.disabled = false;
    dom.processBtn.textContent = 'Enhance';
    resetResults();
}

function formatSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let s = bytes;
    for (const u of units) {
        if (s < 1024) return `${s.toFixed(1)} ${u}`;
        s /= 1024;
    }
    return `${s.toFixed(1)} TB`;
}

// ── one-click processing ──
dom.processBtn.addEventListener('click', startProcessing);
dom.retryBtn.addEventListener('click', startProcessing);
dom.newTaskBtn.addEventListener('click', resetAll);

async function startProcessing() {
    if (!state.file || state.isProcessing) return;
    state.isProcessing = true;
    dom.processBtn.disabled = true;
    resetResults();

    const isVideo = state.file.type.startsWith('video/');
    const endpoint = isVideo ? '/api/enhance/video' : '/api/enhance/image';

    // show progress
    dom.progressSection.classList.remove('hidden');
    dom.progressFill.style.width = '5%';
    dom.progressText.textContent = 'Uploading...';

    const formData = new FormData();
    formData.append('file', state.file);

    try {
        const resp = await fetch(endpoint, { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.error) { showError(data.error); return; }

        state.taskId = data.task_id;
        pollTask();
    } catch (err) {
        showError('Upload failed: ' + err.message);
    }
}

// ── poll ──
function pollTask() {
    if (!state.taskId) return;
    state.pollTimer = setInterval(async () => {
        try {
            const resp = await fetch(`/api/task/${state.taskId}`);
            const data = await resp.json();
            if (data.status === 'error') {
                clearInterval(state.pollTimer);
                showError(data.error);
                return;
            }
            if (data.status === 'processing') {
                const pct = data.progress_pct || 10;
                dom.progressFill.style.width = Math.min(pct, 90) + '%';
                dom.progressText.textContent = data.progress ? `Frames: ${data.progress}` : 'Enhancing...';
                return;
            }
            if (data.status === 'done') {
                clearInterval(state.pollTimer);
                dom.progressFill.style.width = '100%';
                dom.progressText.textContent = 'Done!';
                setTimeout(() => showResult(data), 400);
                return;
            }
        } catch (err) {
            clearInterval(state.pollTimer);
            showError('Poll failed: ' + err.message);
        }
    }, 800);
}

// ── result ──
function showResult(data) {
    dom.progressSection.classList.add('hidden');
    dom.resultSection.classList.remove('hidden');

    const isVideo = /\.(mp4|avi|mov|mkv|webm)/i.test(data.enhanced);

    dom.resultContainer.innerHTML = '';

    const origPane = document.createElement('div');
    origPane.className = 'result-pane';
    origPane.innerHTML = '<h3>Original</h3>' + mediaEl(data.original, isVideo);
    dom.resultContainer.appendChild(origPane);

    const enhPane = document.createElement('div');
    enhPane.className = 'result-pane';
    enhPane.innerHTML = `<h3>Enhanced (Auto)</h3>` + mediaEl(data.enhanced, isVideo);
    dom.resultContainer.appendChild(enhPane);

    // also update compare view if it's an image
    if (!isVideo) {
        const cmpSection = $('#compareSection');
        cmpSection.classList.remove('hidden');
        $('#compareOriginal').src = data.original;
        $('#compareEnhanced').src = data.enhanced;
    }

    dom.downloadBtn.href = data.enhanced;
    dom.downloadBtn.download = data.enhanced.split('/').pop();

    // show analysis if available
    if (data.analysis) {
        renderAnalysis(data.analysis);
    }

    state.isProcessing = false;
    dom.processBtn.disabled = false;
}

function mediaEl(src, isVideo) {
    return isVideo ? `<video controls src="${src}"></video>` : `<img src="${src}" alt="">`;
}

function renderAnalysis(analysis) {
    const section = $('#analyzeSection');
    section.classList.remove('hidden');
    const grid = $('#analyzeGrid');
    const lvlClass = 'level-' + analysis.level;
    const lvlLabels = { extreme: 'Extreme - very dark', severe: 'Very dark', moderate: 'Slightly dark', mild: 'Normal / Slight' };

    grid.innerHTML = `
        <div class="analyze-item"><div class="analyze-label">Mean Lum</div><div class="analyze-value">${analysis.mean_lum.toFixed(1)}</div></div>
        <div class="analyze-item"><div class="analyze-label">Median Lum</div><div class="analyze-value">${analysis.median_lum.toFixed(1)}</div></div>
        <div class="analyze-item"><div class="analyze-label">Dark Pixels</div><div class="analyze-value">${(analysis.dark_ratio*100).toFixed(1)}%</div></div>
        <div class="analyze-item"><div class="analyze-label">Contrast</div><div class="analyze-value">${analysis.contrast.toFixed(1)}</div></div>
        <div class="analyze-item"><div class="analyze-label">Dynamic Range</div><div class="analyze-value">${analysis.dyn_range.toFixed(1)}</div></div>
        <div class="analyze-level ${lvlClass}">${lvlLabels[analysis.level] || analysis.level}</div>
    `;
}

// ── error ──
function showError(msg) {
    dom.progressSection.classList.add('hidden');
    dom.resultSection.classList.add('hidden');
    dom.errorSection.classList.remove('hidden');
    dom.errorMsg.textContent = msg;
    state.isProcessing = false;
    dom.processBtn.disabled = false;
}

// ── reset ──
function resetResults() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
    dom.progressSection.classList.add('hidden');
    dom.resultSection.classList.add('hidden');
    dom.errorSection.classList.add('hidden');
    dom.compareSection?.classList?.add('hidden');
    dom.analyzeSection.classList.add('hidden');
}

function resetAll() {
    resetResults();
    state.file = null;
    state.taskId = null;
    state.isProcessing = false;
    dom.fileInput.value = '';
    dom.uploadArea.classList.remove('hidden');
    dom.filePreview.classList.add('hidden');
    dom.processBtn.disabled = true;
    dom.processBtn.textContent = 'Enhance';
}

// ═══════════════════════════════════════════════════════════════
// Lightbox — click to zoom, arrow keys to switch, ESC to close
// ═══════════════════════════════════════════════════════════════

const lightbox = {
    images: [],      // [{src, label}]
    index: 0,
    el: {
        box: $('#lightbox'),
        bg: $('#lightboxBg'),
        img: $('#lightboxImg'),
        label: $('#lightboxLabel'),
        close: $('#lightboxClose'),
        prev: $('#lightboxPrev'),
        next: $('#lightboxNext'),
    },
    open(images, startIdx) {
        if (!images.length) return;
        this.images = images;
        this.index = Math.max(0, Math.min(startIdx, images.length - 1));
        this.render();
        this.el.box.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    },
    close() {
        this.el.box.classList.add('hidden');
        document.body.style.overflow = '';
        this.images = [];
    },
    render() {
        const cur = this.images[this.index];
        this.el.img.src = cur.src;
        this.el.label.textContent = cur.label;
        this.el.prev.style.visibility = this.images.length > 1 ? '' : 'hidden';
        this.el.next.style.visibility = this.images.length > 1 ? '' : 'hidden';
    },
    prev() {
        if (this.images.length <= 1) return;
        this.index = (this.index - 1 + this.images.length) % this.images.length;
        this.render();
    },
    next() {
        if (this.images.length <= 1) return;
        this.index = (this.index + 1) % this.images.length;
        this.render();
    },
};

// click events
lightbox.el.close.addEventListener('click', () => lightbox.close());
lightbox.el.bg.addEventListener('click', () => lightbox.close());
lightbox.el.prev.addEventListener('click', (e) => { e.stopPropagation(); lightbox.prev(); });
lightbox.el.next.addEventListener('click', (e) => { e.stopPropagation(); lightbox.next(); });
lightbox.el.img.addEventListener('click', (e) => { e.stopPropagation(); });

// keyboard
document.addEventListener('keydown', (e) => {
    if (lightbox.el.box.classList.contains('hidden')) return;
    if (e.key === 'Escape') { lightbox.close(); return; }
    if (e.key === 'ArrowLeft') { lightbox.prev(); return; }
    if (e.key === 'ArrowRight') { lightbox.next(); return; }
});

// ── bind lightbox to result images & compare images ──
function initLightboxTriggers() {
    // Bind to result panes — delegate from resultContainer
    const resultContainer = $('#resultContainer');
    resultContainer.addEventListener('click', (e) => {
        const img = e.target.closest('img');
        if (!img) return;
        const pane = img.closest('.result-pane');
        const h3 = pane ? pane.querySelector('h3') : null;
        const label = h3 ? h3.textContent : 'Image';

        // collect all images currently in result
        const imgs = [...resultContainer.querySelectorAll('img')];
        const list = imgs.map((el, i) => ({
            src: el.src,
            label: el.closest('.result-pane')?.querySelector('h3')?.textContent || `Image ${i + 1}`,
        }));
        const idx = imgs.indexOf(img);
        lightbox.open(list, idx >= 0 ? idx : 0);
    });

    // Bind to compare section
    const compareSection = $('#compareSection');
    compareSection.addEventListener('click', (e) => {
        const img = e.target.closest('img');
        if (!img) return;
        const imgs = [...compareSection.querySelectorAll('img')];
        const list = imgs.map((el, i) => ({
            src: el.src,
            label: el.closest('.compare-pane')?.querySelector('h3')?.textContent || `Image ${i + 1}`,
        }));
        const idx = imgs.indexOf(img);
        lightbox.open(list, idx >= 0 ? idx : 0);
    });
}

// call once on page load
initLightboxTriggers();
