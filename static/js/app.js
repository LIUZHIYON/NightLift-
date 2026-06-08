/**
 * 低光照增强系统 — 前端交互逻辑
 */

// ═══════════════════════════════════════════════════════════════
// 状态
// ═══════════════════════════════════════════════════════════════
const state = {
    file: null,
    selectedMethod: 'comprehensive',
    taskId: null,
    pollTimer: null,
    isProcessing: false,
};

// ═══════════════════════════════════════════════════════════════
// DOM 引用
// ═══════════════════════════════════════════════════════════════
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
    uploadArea: $('#uploadArea'),
    fileInput: $('#fileInput'),
    selectBtn: $('#selectBtn'),
    filePreview: $('#filePreview'),
    fileIcon: $('#fileIcon'),
    fileName: $('#fileName'),
    fileSize: $('#fileSize'),
    changeBtn: $('#changeBtn'),
    methodGrid: $('#methodGrid'),
    processBtn: $('#processBtn'),
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

// ═══════════════════════════════════════════════════════════════
// 文件选择
// ═══════════════════════════════════════════════════════════════

dom.selectBtn.addEventListener('click', () => dom.fileInput.click());
dom.uploadArea.addEventListener('click', (e) => {
    if (e.target !== dom.selectBtn) dom.fileInput.click();
});
dom.fileInput.addEventListener('change', handleFileSelect);

// 拖放支持
dom.uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    dom.uploadArea.classList.add('drag-over');
});
dom.uploadArea.addEventListener('dragleave', () => {
    dom.uploadArea.classList.remove('drag-over');
});
dom.uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    dom.uploadArea.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) setFile(files[0]);
});

dom.changeBtn.addEventListener('click', () => {
    dom.fileInput.value = '';
    dom.fileInput.click();
});

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) setFile(files[0]);
}

function setFile(file) {
    state.file = file;
    dom.fileName.textContent = file.name;
    dom.fileSize.textContent = formatSize(file.size);

    const isVideo = file.type.startsWith('video/');
    dom.fileIcon.textContent = isVideo ? '🎬' : '🖼️';

    dom.uploadArea.classList.add('hidden');
    dom.filePreview.classList.remove('hidden');
    dom.processBtn.disabled = false;
    dom.processBtn.textContent = isVideo ? '🚀 开始增强视频' : '🚀 开始增强图片';

    // 重置结果
    resetResults();
}

function formatSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    for (const u of units) {
        if (size < 1024) return `${size.toFixed(1)} ${u}`;
        size /= 1024;
    }
    return `${size.toFixed(1)} TB`;
}

// ═══════════════════════════════════════════════════════════════
// 方法选择
// ═══════════════════════════════════════════════════════════════

dom.methodGrid.addEventListener('click', (e) => {
    const card = e.target.closest('.method-card');
    if (!card) return;
    dom.methodGrid.querySelectorAll('.method-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    state.selectedMethod = card.dataset.method;
});

// ═══════════════════════════════════════════════════════════════
// 开始处理
// ═══════════════════════════════════════════════════════════════

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

    // 显示进度
    dom.progressSection.classList.remove('hidden');
    dom.progressFill.style.width = '10%';
    dom.progressText.textContent = '正在上传...';

    const formData = new FormData();
    formData.append('file', state.file);
    formData.append('method', state.selectedMethod);

    try {
        const resp = await fetch(endpoint, { method: 'POST', body: formData });
        const data = await resp.json();

        if (data.error) {
            showError(data.error);
            return;
        }

        state.taskId = data.task_id;
        pollTask();
    } catch (err) {
        showError('上传失败: ' + err.message);
    }
}

// ═══════════════════════════════════════════════════════════════
// 轮询任务状态
// ═══════════════════════════════════════════════════════════════

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
                if (data.progress) {
                    dom.progressText.textContent = `已处理 ${data.progress} 帧...`;
                } else {
                    dom.progressText.textContent = '正在增强...';
                }
                return;
            }

            if (data.status === 'done') {
                clearInterval(state.pollTimer);
                dom.progressFill.style.width = '100%';
                dom.progressText.textContent = '处理完成！';
                setTimeout(() => showResult(data), 400);
                return;
            }
        } catch (err) {
            clearInterval(state.pollTimer);
            showError('查询状态失败: ' + err.message);
        }
    }, 800);
}

// ═══════════════════════════════════════════════════════════════
// 显示结果
// ═══════════════════════════════════════════════════════════════

function showResult(data) {
    dom.progressSection.classList.add('hidden');
    dom.resultSection.classList.remove('hidden');

    const isVideo = data.enhanced.endsWith('.mp4') ||
                    /\.(avi|mov|mkv|webm)/i.test(data.enhanced);

    dom.resultContainer.innerHTML = '';

    // 原始文件
    const origPane = document.createElement('div');
    origPane.className = 'result-pane';
    origPane.innerHTML = `<h3>📥 原始文件</h3>` + mediaEl(data.original, isVideo);
    dom.resultContainer.appendChild(origPane);

    // 增强文件
    const enhPane = document.createElement('div');
    enhPane.className = 'result-pane';
    enhPane.innerHTML = `<h3>✨ 增强结果 (${data.method_name})</h3>` + mediaEl(data.enhanced, isVideo);
    dom.resultContainer.appendChild(enhPane);

    // 下载按钮
    dom.downloadBtn.href = data.enhanced;
    dom.downloadBtn.download = data.enhanced.split('/').pop();

    state.isProcessing = false;
    dom.processBtn.disabled = false;
}

function mediaEl(src, isVideo) {
    if (isVideo) {
        return `<video controls src="${src}"></video>`;
    }
    return `<img src="${src}" alt="增强结果">`;
}

// ═══════════════════════════════════════════════════════════════
// 错误
// ═══════════════════════════════════════════════════════════════

function showError(msg) {
    dom.progressSection.classList.add('hidden');
    dom.resultSection.classList.add('hidden');
    dom.errorSection.classList.remove('hidden');
    dom.errorMsg.textContent = msg;
    state.isProcessing = false;
    dom.processBtn.disabled = false;
}

// ═══════════════════════════════════════════════════════════════
// 重置
// ═══════════════════════════════════════════════════════════════

function resetResults() {
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
    dom.progressSection.classList.add('hidden');
    dom.resultSection.classList.add('hidden');
    dom.errorSection.classList.add('hidden');
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
    dom.processBtn.textContent = '🚀 开始增强';
}
