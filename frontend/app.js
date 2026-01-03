/**
 * AI Model Generator - Frontend Application
 */

let API_BASE = 'http://localhost:8000/api';
const POLLING_INTERVAL = 2000;

function computeDefaultApiBase() {
    const host = window.location.hostname;
    const isLocal = host === 'localhost' || host === '127.0.0.1';
    if (isLocal) return 'http://localhost:8000/api';
    // If you deploy a backend on the same domain with a rewrite, this will work:
    return `${window.location.origin}/api`;
}

function setApiBase(url) {
    const value = (url || '').trim();
    if (!value) {
        API_BASE = computeDefaultApiBase();
        return;
    }
    // Normalize: remove trailing slash
    API_BASE = value.replace(/\/$/, '');
}

function getBackendOrigin() {
    try {
        return new URL(API_BASE).origin;
    } catch {
        return 'http://localhost:8000';
    }
}

// ============================================
// State Management
// ============================================

const state = {
    currentCategory: 'image',
    currentJob: null,
    pollingTimer: null,
    language: localStorage.getItem('language') || 'it',
    theme: localStorage.getItem('theme') || 'dark',
    uploadedFiles: {
        face: [],
        video: null,
        videoMotion: null,
        lipsync: null
    },
    settings: {
        apiBaseUrl: '',
        replicateKey: '',
        lipsyncProvider: 'elevenlabs',
        elevenLabsKey: '',
        syncLabsKey: '',
        didKey: ''
    }
};

// ============================================
// DOM Elements
// ============================================

const elements = {
    // Navigation
    navItems: document.querySelectorAll('.nav-item'),
    panels: document.querySelectorAll('.panel'),
    
    // Forms
    faceForm: document.getElementById('face-form'),
    videoForm: document.getElementById('video-form'),
    lipsyncForm: document.getElementById('lipsync-form'),
    settingsForm: document.getElementById('settings-form'),
    
    // Results
    jobStatus: document.getElementById('job-status'),
    resultDisplay: document.getElementById('result-display'),
    progressFill: document.getElementById('progress-fill'),
    statusMessage: document.getElementById('status-message'),
    statusTime: document.getElementById('status-time'),
    resultImage: document.getElementById('result-image'),
    resultVideo: document.getElementById('result-video'),
    downloadLink: document.getElementById('download-link'),
    continueBtn: document.getElementById('continue-btn'),
    historyList: document.getElementById('history-list'),
    
    // Toast
    toastContainer: document.getElementById('toast-container'),
    
    // Theme & Language
    themeToggle: document.getElementById('theme-toggle'),
    langButtons: document.querySelectorAll('.lang-btn')
};

// ============================================
// Internationalization (i18n)
// ============================================

function initI18n() {
    setLanguage(state.language);
    
    // Language button handlers
    elements.langButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const lang = btn.dataset.lang;
            setLanguage(lang);
        });
    });
}

function setLanguage(lang) {
    state.language = lang;
    localStorage.setItem('language', lang);
    
    // Update active button
    elements.langButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.lang === lang);
    });
    
    // Update HTML lang attribute
    document.documentElement.lang = lang;
    
    // Translate all elements
    translatePage();
}

function translatePage() {
    const t = window.translations[state.language] || window.translations.en;
    
    // Translate elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        if (t[key]) {
            el.textContent = t[key];
        }
    });
    
    // Translate placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.dataset.i18nPlaceholder;
        if (t[key]) {
            el.placeholder = t[key];
        }
    });
    
    // Update theme button text
    const themeText = elements.themeToggle.querySelector('.theme-text');
    if (themeText) {
        themeText.textContent = state.theme === 'dark' ? t.darkMode : t.lightMode;
    }
}

function t(key) {
    const translations = window.translations[state.language] || window.translations.en;
    return translations[key] || key;
}

// ============================================
// Theme Management
// ============================================

function initTheme() {
    setTheme(state.theme);
    
    elements.themeToggle.addEventListener('click', () => {
        const newTheme = state.theme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
    });
}

function setTheme(theme) {
    state.theme = theme;
    localStorage.setItem('theme', theme);
    document.documentElement.dataset.theme = theme;
    
    // Update button text
    const themeText = elements.themeToggle.querySelector('.theme-text');
    if (themeText) {
        const translations = window.translations[state.language] || window.translations.en;
        themeText.textContent = theme === 'dark' ? translations.darkMode : translations.lightMode;
    }
}

// ============================================
// Navigation
// ============================================

function initNavigation() {
    elements.navItems.forEach(item => {
        item.addEventListener('click', () => {
            const category = item.dataset.category;
            switchCategory(category);
        });
    });
}

function switchCategory(category) {
    state.currentCategory = category;
    
    // Update nav items
    elements.navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.category === category);
    });
    
    // Update panels
    elements.panels.forEach(panel => {
        const panelId = `${category}-panel`;
        panel.classList.toggle('active', panel.id === panelId);
    });
}

// ============================================
// Settings Management
// ============================================

function initSettings() {
    // Load saved settings
    loadSettings();
    setApiBase(state.settings.apiBaseUrl || '');
    
    // Provider tabs
    document.querySelectorAll('.provider-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const provider = tab.dataset.provider;
            
            // Update tabs
            document.querySelectorAll('.provider-tab').forEach(t => {
                t.classList.toggle('active', t.dataset.provider === provider);
            });
            
            // Update config panels
            document.querySelectorAll('.provider-config').forEach(config => {
                config.classList.toggle('active', config.id === `config-${provider}`);
            });
            
            state.settings.lipsyncProvider = provider;
        });
    });
    
    // Toggle visibility buttons
    document.querySelectorAll('.toggle-visibility').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = btn.previousElementSibling;
            if (input.type === 'password') {
                input.type = 'text';
                btn.querySelector('svg').innerHTML = `
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                `;
            } else {
                input.type = 'password';
                btn.querySelector('svg').innerHTML = `
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                `;
            }
        });
    });
    
    // Settings form submit
    elements.settingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        saveSettings();
        const ok = await sendSettingsToBackend();
        if (ok) {
            showToast(t('settingsSaved'), 'success');
        } else {
            showToast('Failed to reach backend. Check Backend API URL.', 'error');
        }
    });
}

function loadSettings() {
    const saved = localStorage.getItem('apiSettings');
    if (saved) {
        try {
            const settings = JSON.parse(saved);
            state.settings = { ...state.settings, ...settings };
            
            // Populate form fields
            const apiBaseInput = document.getElementById('api-base-url');
            if (apiBaseInput) apiBaseInput.value = settings.apiBaseUrl || '';

            const replicateInput = document.getElementById('replicate-key');
            if (replicateInput) replicateInput.value = settings.replicateKey || '';

            const faceModelInput = document.getElementById('face-model');
            if (faceModelInput) faceModelInput.value = settings.faceModel || '';

            const videoModelInput = document.getElementById('video-model');
            if (videoModelInput) videoModelInput.value = settings.videoModel || '';
            
            const elevenLabsInput = document.getElementById('elevenlabs-key');
            if (elevenLabsInput) elevenLabsInput.value = settings.elevenLabsKey || '';
            
            const syncLabsInput = document.getElementById('synclabs-key');
            if (syncLabsInput) syncLabsInput.value = settings.syncLabsKey || '';
            
            const didInput = document.getElementById('did-key');
            if (didInput) didInput.value = settings.didKey || '';
            
            // Set active provider tab
            if (settings.lipsyncProvider) {
                document.querySelectorAll('.provider-tab').forEach(tab => {
                    tab.classList.toggle('active', tab.dataset.provider === settings.lipsyncProvider);
                });
                document.querySelectorAll('.provider-config').forEach(config => {
                    config.classList.toggle('active', config.id === `config-${settings.lipsyncProvider}`);
                });
            }
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
    }
}

function saveSettings() {
    const apiBaseInput = document.getElementById('api-base-url');
    const replicateInput = document.getElementById('replicate-key');
    const faceModelInput = document.getElementById('face-model');
    const videoModelInput = document.getElementById('video-model');
    const elevenLabsInput = document.getElementById('elevenlabs-key');
    const syncLabsInput = document.getElementById('synclabs-key');
    const didInput = document.getElementById('did-key');
    
    state.settings = {
        apiBaseUrl: apiBaseInput ? apiBaseInput.value : '',
        replicateKey: replicateInput ? replicateInput.value : '',
        faceModel: faceModelInput ? faceModelInput.value : '',
        videoModel: videoModelInput ? videoModelInput.value : '',
        lipsyncProvider: document.querySelector('.provider-tab.active')?.dataset.provider || 'elevenlabs',
        elevenLabsKey: elevenLabsInput ? elevenLabsInput.value : '',
        syncLabsKey: syncLabsInput ? syncLabsInput.value : '',
        didKey: didInput ? didInput.value : ''
    };
    
    localStorage.setItem('apiSettings', JSON.stringify(state.settings));
    setApiBase(state.settings.apiBaseUrl || '');
}

async function sendSettingsToBackend() {
    try {
        const res = await fetch(`${API_BASE}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state.settings)
        });
        return res.ok;
    } catch (e) {
        console.log('Settings saved locally (backend not available)');
        return false;
    }
}

// ============================================
// Image Upload Handlers
// ============================================

function initImageUploads() {
    // Face reference images
    document.querySelectorAll('.image-upload-slot').forEach(slot => {
        const slotNum = slot.dataset.slot;
        const input = document.getElementById(`ref-image-${slotNum}`);
        const preview = slot.querySelector('.preview-image');
        const placeholder = slot.querySelector('.upload-placeholder');
        const removeBtn = slot.querySelector('.remove-image');
        
        slot.addEventListener('click', (e) => {
            if (e.target !== removeBtn) {
                input.click();
            }
        });
        
        input.addEventListener('change', () => {
            if (input.files[0]) {
                const file = input.files[0];
                const reader = new FileReader();
                
                reader.onload = (e) => {
                    preview.src = e.target.result;
                    preview.hidden = false;
                    placeholder.hidden = true;
                    removeBtn.hidden = false;
                    state.uploadedFiles.face[slotNum - 1] = file;
                };
                
                reader.readAsDataURL(file);
            }
        });
        
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            input.value = '';
            preview.hidden = true;
            placeholder.hidden = false;
            removeBtn.hidden = true;
            state.uploadedFiles.face[slotNum - 1] = null;
        });
    });
    
    // Video source image
    initSingleUpload('video-source', 'video-upload-area', 'video-source-preview', 'video', true);
    initSingleUpload('video-motion', 'video-motion-upload-area', 'video-motion-preview', 'videoMotion', false);
    
    // Lipsync video
    initSingleUpload('lipsync-video', 'lipsync-upload-area', 'lipsync-video-preview', 'lipsync', false);
}

function initSingleUpload(inputId, areaId, previewId, stateKey, isImage) {
    const input = document.getElementById(inputId);
    const area = document.getElementById(areaId);
    const preview = document.getElementById(previewId);
    const previewContainer = preview.parentElement;
    const removeBtn = previewContainer.querySelector('.remove-upload');
    
    area.addEventListener('click', () => input.click());
    
    // Drag and drop
    area.addEventListener('dragover', (e) => {
        e.preventDefault();
        area.classList.add('dragover');
    });
    
    area.addEventListener('dragleave', () => {
        area.classList.remove('dragover');
    });
    
    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.classList.remove('dragover');
        
        if (e.dataTransfer.files[0]) {
            input.files = e.dataTransfer.files;
            handleFileSelect(input, area, preview, previewContainer, stateKey, isImage);
        }
    });
    
    input.addEventListener('change', () => {
        handleFileSelect(input, area, preview, previewContainer, stateKey, isImage);
    });
    
    removeBtn.addEventListener('click', () => {
        input.value = '';
        area.hidden = false;
        previewContainer.hidden = true;
        state.uploadedFiles[stateKey] = null;
    });
}

function handleFileSelect(input, area, preview, previewContainer, stateKey, isImage) {
    if (input.files[0]) {
        const file = input.files[0];
        
        if (isImage) {
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
            };
            reader.readAsDataURL(file);
        } else {
            preview.src = URL.createObjectURL(file);
        }
        
        area.hidden = true;
        previewContainer.hidden = false;
        state.uploadedFiles[stateKey] = file;
    }
}

// ============================================
// Form Handlers
// ============================================

function initForms() {
    // Face generation form
    elements.faceForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitFaceGeneration();
    });
    
    // Video generation form
    elements.videoForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitVideoGeneration();
    });
    
    // Lipsync form
    elements.lipsyncForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitLipsyncGeneration();
    });
    
    // Character count
    const lipsyncText = document.getElementById('lipsync-text');
    const charCount = document.getElementById('char-count');
    
    lipsyncText.addEventListener('input', () => {
        charCount.textContent = lipsyncText.value.length;
    });
    
    // Continue button
    elements.continueBtn.addEventListener('click', () => {
        if (state.currentJob?.job_type === 'face' && state.currentJob?.result_url) {
            switchCategory('video');
            showToast(t('continueToVideo'), 'info');
        }
    });
}

async function submitFaceGeneration() {
    const form = elements.faceForm;
    const btn = form.querySelector('.generate-btn');
    
    try {
        setButtonLoading(btn, true);
        
        const formData = new FormData();
        formData.append('prompt', document.getElementById('face-prompt').value);
        formData.append('aspect_ratio', document.getElementById('face-aspect').value);
        
        // Add reference images
        state.uploadedFiles.face.forEach((file, index) => {
            if (file) {
                formData.append('images', file);
            }
        });
        
        const response = await fetch(`${API_BASE}/face/generate`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Generation failed');
        }
        
        const data = await response.json();
        showToast(t('processing') + '...', 'success');
        startJobPolling(data.job_id, 'face');
        
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

async function submitVideoGeneration() {
    const form = elements.videoForm;
    const btn = form.querySelector('.generate-btn');
    
    if (!state.uploadedFiles.video) {
        showToast(t('startImage') + ' ' + t('required'), 'error');
        return;
    }
    if (!state.uploadedFiles.videoMotion) {
        showToast(t('drivingVideo') + ' ' + t('required'), 'error');
        return;
    }
    
    try {
        setButtonLoading(btn, true);
        
        const formData = new FormData();
        formData.append('image', state.uploadedFiles.video);
        formData.append('video', state.uploadedFiles.videoMotion);

        const mode = document.getElementById('video-mode')?.value || 'std';
        formData.append('mode', mode);

        const orientation = document.getElementById('video-orientation')?.value || 'video';
        formData.append('character_orientation', orientation);

        const keepSound = document.getElementById('video-keep-sound')?.checked ? 'true' : 'false';
        formData.append('keep_original_sound', keepSound);

        formData.append('prompt', document.getElementById('video-prompt').value || '');
        
        const response = await fetch(`${API_BASE}/video/generate`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Generation failed');
        }
        
        const data = await response.json();
        showToast(t('processing') + '...', 'success');
        startJobPolling(data.job_id, 'video');
        
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

async function submitLipsyncGeneration() {
    const form = elements.lipsyncForm;
    const btn = form.querySelector('.generate-btn');
    
    if (!state.uploadedFiles.lipsync) {
        showToast(t('sourceVideo') + ' ' + t('required'), 'error');
        return;
    }
    
    const text = document.getElementById('lipsync-text').value;
    if (!text.trim()) {
        showToast(t('speechText') + ' ' + t('required'), 'error');
        return;
    }
    
    try {
        setButtonLoading(btn, true);
        
        const formData = new FormData();
        formData.append('video', state.uploadedFiles.lipsync);
        formData.append('text', text);
        formData.append('voice_type', document.getElementById('voice-type').value);
        formData.append('language', document.getElementById('voice-language').value);
        
        const response = await fetch(`${API_BASE}/lipsync/generate`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Generation failed');
        }
        
        const data = await response.json();
        showToast(t('processing') + '...', 'success');
        startJobPolling(data.job_id, 'lipsync');
        
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

// ============================================
// Job Polling
// ============================================

function startJobPolling(jobId, jobType) {
    // Clear previous polling
    if (state.pollingTimer) {
        clearInterval(state.pollingTimer);
    }
    
    state.currentJob = { job_id: jobId, job_type: jobType };
    
    // Show status panel
    elements.jobStatus.hidden = false;
    elements.resultDisplay.hidden = true;
    
    const demoSection = document.querySelector('.demo-section');
    if (demoSection) {
        demoSection.hidden = true;
    }
    
    // Update status badge
    const statusBadge = elements.jobStatus.querySelector('.status-badge');
    statusBadge.className = 'status-badge processing';
    statusBadge.textContent = t('processing');
    
    let startTime = Date.now();
    
    // Start polling
    const poll = async () => {
        try {
            const response = await fetch(`${API_BASE}/jobs/${jobId}`);
            
            if (!response.ok) {
                throw new Error('Failed to get job status');
            }
            
            const job = await response.json();
            
            // Update progress
            elements.progressFill.style.width = `${job.progress}%`;
            elements.statusMessage.textContent = job.message;
            
            // Update time
            const elapsed = Math.round((Date.now() - startTime) / 1000);
            elements.statusTime.textContent = `${elapsed}s`;
            
            // Check status
            if (job.status === 'completed') {
                clearInterval(state.pollingTimer);
                statusBadge.className = 'status-badge completed';
                statusBadge.textContent = t('completed');
                
                showResult(job);
                showToast(t('completed') + '!', 'success');
                addToHistory(job);
                
            } else if (job.status === 'failed') {
                clearInterval(state.pollingTimer);
                statusBadge.className = 'status-badge failed';
                statusBadge.textContent = t('failed');
                
                showToast(job.error || t('failed'), 'error');
            }
            
            state.currentJob = job;
            
        } catch (error) {
            console.error('Polling error:', error);
        }
    };
    
    // Initial poll
    poll();
    
    // Set up interval
    state.pollingTimer = setInterval(poll, POLLING_INTERVAL);
}

// ============================================
// Result Display
// ============================================

function showResult(job) {
    elements.resultDisplay.hidden = false;
    
    const resultUrl = `${getBackendOrigin()}${job.result_url}`;
    
    if (job.job_type === 'face') {
        elements.resultImage.src = resultUrl;
        elements.resultImage.hidden = false;
        elements.resultVideo.hidden = true;
        elements.continueBtn.hidden = false;
        elements.continueBtn.querySelector('span').textContent = t('continueToVideo');
    } else {
        elements.resultVideo.src = resultUrl;
        elements.resultVideo.hidden = false;
        elements.resultImage.hidden = true;
        
        if (job.job_type === 'video') {
            elements.continueBtn.hidden = false;
            elements.continueBtn.querySelector('span').textContent = t('continueToLipSync');
            elements.continueBtn.onclick = () => {
                switchCategory('lipsync');
                showToast(t('continueToLipSync'), 'info');
            };
        } else {
            elements.continueBtn.hidden = true;
        }
    }
    
    elements.downloadLink.href = resultUrl;
    elements.downloadLink.download = `${job.job_type}_${job.job_id}.${job.job_type === 'face' ? 'png' : 'mp4'}`;
}

// ============================================
// History
// ============================================

function addToHistory(job) {
    const emptyMsg = elements.historyList.querySelector('.history-empty');
    if (emptyMsg) {
        emptyMsg.remove();
    }
    
    const resultUrl = `${getBackendOrigin()}${job.result_url}`;
    const isVideo = job.job_type !== 'face';
    
    const item = document.createElement('div');
    item.className = 'history-item';
    item.innerHTML = `
        ${isVideo 
            ? `<video class="history-thumb" src="${resultUrl}" muted></video>`
            : `<img class="history-thumb" src="${resultUrl}" alt="">`
        }
        <div class="history-info">
            <span class="history-type">${job.job_type}</span>
            <span class="history-time">${new Date().toLocaleTimeString()}</span>
        </div>
    `;
    
    item.addEventListener('click', () => {
        showResult(job);
    });
    
    elements.historyList.insertBefore(item, elements.historyList.firstChild);
    
    // Keep only last 10 items
    while (elements.historyList.children.length > 10) {
        elements.historyList.removeChild(elements.historyList.lastChild);
    }
}

// ============================================
// Utilities
// ============================================

function setButtonLoading(btn, loading) {
    const text = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.btn-loader');
    
    btn.disabled = loading;
    if (text) text.hidden = loading;
    if (loader) loader.hidden = !loading;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        </button>
    `;
    
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => removeToast(toast));
    
    elements.toastContainer.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => removeToast(toast), 5000);
}

function removeToast(toast) {
    toast.style.animation = 'slideOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
}

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// ============================================
// Initialize
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initI18n();
    initNavigation();
    initImageUploads();
    initForms();
    initSettings();
    
    console.log('🎨 AI Model Generator initialized');
    console.log(`📍 Language: ${state.language}`);
    console.log(`🎨 Theme: ${state.theme}`);
});
