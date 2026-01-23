document.addEventListener('DOMContentLoaded', () => {
    const menuBtn = document.getElementById('menu-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn');
    const sidebar = document.getElementById('sidebar');
    const mainContainer = document.getElementById('main-container');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    const sessionList = document.getElementById('session-list');

    // Overlay for mobile sidebars
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    // ==================== Session Expiration Handling ====================

    /**
     * Check if a response indicates session expiration and handle redirect
     * @param {Response} response - The fetch response object
     * @returns {boolean} - True if session was expired and redirect initiated
     */
    async function handleSessionExpiration(response) {
        if (response.status === 401) {
            try {
                const data = await response.clone().json();
                if (data.code === 'SESSION_INVALIDATED' || data.error) {
                    showSessionExpiredNotification(data.error || 'Your session has expired. Please log in again.');
                    return true;
                }
            } catch (e) {
                // If we can't parse JSON, still handle the 401
                showSessionExpiredNotification('Your session has expired. Please log in again.');
                return true;
            }
        }
        return false;
    }

    /**
     * Show a notification about session expiration and redirect to login
     * @param {string} message - The message to display
     */
    function showSessionExpiredNotification(message) {
        // Create and show a notification overlay
        const overlay = document.createElement('div');
        overlay.className = 'session-expired-overlay';
        overlay.innerHTML = `
            <div class="session-expired-modal">
                <div class="session-expired-icon">
                    <i class="fa-solid fa-clock"></i>
                </div>
                <h3>Session Expired</h3>
                <p>${message}</p>
                <button class="session-expired-btn" onclick="window.location.href='/auth/login'">
                    Log In Again
                </button>
            </div>
        `;
        document.body.appendChild(overlay);

        // Disable chat input to prevent further actions
        if (chatInput) chatInput.disabled = true;
        if (sendBtn) sendBtn.disabled = true;

        // Auto-redirect after 3 seconds
        setTimeout(() => {
            window.location.href = '/auth/login';
        }, 3000);
    }

    // ==================== End Session Expiration Handling ====================

    // Settings and profile buttons in left sidebar
    const settingsBtn = document.getElementById('settings-btn');
    const profileBtn = document.getElementById('profile-btn');
    const logoutBtnSidebar = document.getElementById('logout-btn');
    const currentModelDisplay = document.getElementById('current-model-display');
    const currentModelIcon = document.getElementById('current-model-icon');
    const loadedModelId = document.getElementById('loaded-model-id');
    const welcomeMessage = document.getElementById('welcome-message');
    const scrollToBottomBtn = document.getElementById('scroll-to-bottom-btn');

    let isBotTyping = false;
    let currentAbortController = null; // For stopping LLM responses
    let typingIndicatorElement = null; // Reference to typing indicator

    // Check start fresh preference on page load (default to true if not set)
    const startFreshValue = localStorage.getItem('startFreshSession');
    const startFreshEnabled = startFreshValue === null ? true : startFreshValue === 'true';
    let currentSessionId = startFreshEnabled ? null : localStorage.getItem('session_id');

    // If start fresh is enabled, clear the stored session
    if (startFreshEnabled) {
        localStorage.removeItem('session_id');
    }

    let currentModel = null;
    let currentProvider = null;

    // File attachment handling
    const attachFileBtn = document.getElementById('attach-file-btn');
    const fileInput = document.getElementById('file-input');
    const attachmentPreviewContainer = document.getElementById('attachment-preview-container');
    let pendingAttachments = []; // Stores uploaded file info

    // Vision toggle for local models
    const visionToggleBtn = document.getElementById('vision-toggle-btn');
    let localVisionEnabled = localStorage.getItem('localVisionEnabled') === 'true';

    // Store reference to welcome message HTML to recreate it if needed
    let welcomeMessageHTML = welcomeMessage ? welcomeMessage.outerHTML : null;

    // Function to toggle welcome message visibility
    function toggleWelcomeMessage() {
        // Get current welcome message element (may have been re-added)
        const currentWelcome = document.getElementById('welcome-message');

        // Count actual chat messages (exclude welcome message and typing indicator)
        const messageCount = chatMessages.querySelectorAll('.message:not(.typing-indicator)').length;

        if (currentWelcome) {
            if (messageCount === 0) {
                currentWelcome.style.display = 'flex';
            } else {
                currentWelcome.style.display = 'none';
            }
        }
    }

    // Function to ensure welcome message exists
    function ensureWelcomeMessage() {
        if (!document.getElementById('welcome-message') && welcomeMessageHTML) {
            chatMessages.insertAdjacentHTML('afterbegin', welcomeMessageHTML);
        }
    }

    // Model display names
    const modelDisplayNames = {
        'gemini': 'Gemini',
        'xai': 'Grok',
        'anthropic': 'Claude',
        'openai': 'ChatGPT',
        'simply_lm_studio': 'LM Studio',
        'simply_ollama': 'Ollama'
    };

    // Model icon paths
    const modelIcons = {
        'gemini': '/static/images/gemini.png',
        'xai': '/static/images/grok.png',
        'anthropic': '/static/images/claude.png',
        'openai': '/static/images/chatgpt.png',
        'simply_lm_studio': '/static/images/lmstudio.png',
        'simply_ollama': '/static/images/ollama.png'
    };

    // Theme Management
    function initTheme() {
        // Get saved theme or default to light
        const savedTheme = localStorage.getItem('theme') || 'light';
        setTheme(savedTheme);
    }

    function setTheme(theme) {
        if (theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            switchPrismTheme('dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
            switchPrismTheme('light');
        }
        localStorage.setItem('theme', theme);
    }

    // Function to switch Prism.js theme
    function switchPrismTheme(theme) {
        const lightTheme = document.getElementById('prism-theme-light');
        const darkTheme = document.getElementById('prism-theme-dark');

        if (theme === 'dark') {
            lightTheme.disabled = true;
            darkTheme.disabled = false;
        } else {
            lightTheme.disabled = false;
            darkTheme.disabled = true;
        }

        // Re-highlight all code blocks with the new theme
        if (window.Prism) {
            setTimeout(() => {
                document.querySelectorAll('pre code[class*="language-"]').forEach((block) => {
                    Prism.highlightElement(block);
                });
            }, 50);
        }
    }

    // Initialize theme on page load
    initTheme();

    // Initialize textarea height
    resetTextareaHeight();


    // ==================== File Attachment Handling ====================

    function formatFileSize(bytes) {
        const units = ['B', 'KB', 'MB', 'GB'];
        let size = bytes;
        let unitIndex = 0;
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }
        return `${size.toFixed(1)} ${units[unitIndex]}`;
    }

    function getFileIconPath(mimeType) {
        // Normalize mime type (trim and lowercase) to handle variations
        const normalizedMimeType = (mimeType || '').trim().toLowerCase();

        // PDFs - use startsWith to handle parameters like "application/pdf; charset=binary"
        if (normalizedMimeType.startsWith('application/pdf')) {
            return '/static/images/pdf-icon.png';
        }

        // Word documents
        if (normalizedMimeType.includes('word') ||
            normalizedMimeType === 'application/msword' ||
            normalizedMimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
            return '/static/images/word-icon.png';
        }

        // Excel/Spreadsheet documents
        if (normalizedMimeType.includes('excel') ||
            normalizedMimeType.includes('spreadsheet') ||
            normalizedMimeType === 'application/vnd.ms-excel' ||
            normalizedMimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
            return '/static/images/excel-icon.png';
        }

        // CSV files
        if (normalizedMimeType === 'text/csv') {
            return '/static/images/csv-icon.png';
        }

        // Text files (check this last to avoid matching other types)
        if (normalizedMimeType.startsWith('text/')) {
            return '/static/images/text-icon.png';
        }

        // Default fallback for unknown file types
        return '/static/images/generic-file-icon.png';
    }

    function addAttachmentPreview(fileInfo) {
        const preview = document.createElement('div');
        preview.className = 'attachment-preview';
        preview.dataset.filename = fileInfo.stored_filename;

        let content = '';
        if (fileInfo.file_type === 'image') {
            // Show image preview
            const imageUrl = `/api/attachments/${fileInfo.id || 'preview'}`;
            content = `<img src="${URL.createObjectURL(fileInfo.file)}" alt="${fileInfo.original_filename}" class="attachment-preview-image">`;
        } else {
            // Show custom icon for documents
            const iconPath = getFileIconPath(fileInfo.mime_type);
            content = `<div class="attachment-preview-icon"><img src="${iconPath}" alt="File icon" class="file-type-icon"></div>`;
        }

        preview.innerHTML = `
            ${content}
            <div class="attachment-preview-info">
                <div class="attachment-preview-name" title="${fileInfo.original_filename}">${fileInfo.original_filename}</div>
                <div class="attachment-preview-size">${fileInfo.file_size_formatted}</div>
            </div>
            <button class="attachment-remove-btn" title="Remove attachment">
                <i class="fa-solid fa-times"></i>
            </button>
        `;

        preview.querySelector('.attachment-remove-btn').addEventListener('click', () => {
            removeAttachment(fileInfo.stored_filename);
        });

        attachmentPreviewContainer.appendChild(preview);
        attachmentPreviewContainer.style.display = 'flex';
    }

    function removeAttachment(storedFilename) {
        pendingAttachments = pendingAttachments.filter(att => att.stored_filename !== storedFilename);
        const preview = attachmentPreviewContainer.querySelector(`[data-filename="${storedFilename}"]`);
        if (preview) preview.remove();

        if (pendingAttachments.length === 0) {
            attachmentPreviewContainer.style.display = 'none';
        }
    }

    function clearAttachments() {
        pendingAttachments = [];
        attachmentPreviewContainer.innerHTML = '';
        attachmentPreviewContainer.style.display = 'none';
        fileInput.value = '';
    }

    async function uploadFiles(files) {
        for (const file of files) {
            try {
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/api/upload_attachment', {
                    method: 'POST',
                    body: formData
                });

                // Check for session expiration
                if (await handleSessionExpiration(response)) {
                    return;
                }

                const data = await response.json();

                if (response.ok) {
                    const fileInfo = {
                        ...data.file_info,
                        file: file // Store file object for preview
                    };
                    pendingAttachments.push(fileInfo);
                    addAttachmentPreview(fileInfo);
                } else if (response.status === 429) {
                    alert(`Rate limit exceeded. Please wait before uploading more files.`);
                } else {
                    alert(`Failed to upload ${file.name}: ${data.error}`);
                }
            } catch (error) {
                console.error('Upload error:', error);
                alert(`Failed to upload ${file.name}: ${error.message}`);
            }
        }
    }

    function renderAttachmentsInMessage(attachments, messageType = 'bot') {
        if (!attachments || attachments.length === 0) return '';

        let html = '<div class="message-attachments">';
        for (const att of attachments) {
            // Determine the image URL based on whether we have an ID (from database) or file_path (newly uploaded)
            const imageUrl = att.id ? `/api/attachments/${att.id}` : `/uploads/${att.file_path}`;

            // For bot messages with images, show full-size clickable images
            if (att.file_type === 'image' && messageType === 'bot') {
                html += `
                    <div class="message-attachment">
                        <img src="${imageUrl}" alt="${att.original_filename}" class="message-attachment-image" onclick="window.open(this.src, '_blank')">
                    </div>
                `;
            } else if (messageType === 'user' && att.file_type === 'image') {
                // User message images: show as clickable thumbnail
                html += `
                    <div class="message-attachment">
                        <img src="${imageUrl}"
                             alt="${att.original_filename}"
                             class="message-attachment-thumbnail"
                             onclick="window.open(this.src, '_blank')"
                             title="${att.original_filename} (${formatFileSize(att.file_size)})">
                    </div>
                `;
            } else if (messageType === 'user') {
                // User message documents: show as info display (non-clickable)
                const iconPath = getFileIconPath(att.mime_type);
                html += `
                    <div class="message-attachment">
                        <div class="message-attachment-document">
                            <div class="message-attachment-icon">
                                <img src="${iconPath}" alt="File icon" class="file-type-icon">
                            </div>
                            <div class="message-attachment-info">
                                <div class="message-attachment-name">${att.original_filename}</div>
                                <div class="message-attachment-meta">${formatFileSize(att.file_size)} • ${att.mime_type}</div>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                // Bot message documents: keep as downloadable links
                const iconPath = getFileIconPath(att.mime_type);
                const downloadUrl = att.id ? `/api/attachments/${att.id}?download=true` : `/uploads/${att.file_path}`;
                html += `
                    <div class="message-attachment">
                        <a href="${downloadUrl}" class="message-attachment-document">
                            <div class="message-attachment-icon">
                                <img src="${iconPath}" alt="File icon" class="file-type-icon">
                            </div>
                            <div class="message-attachment-info">
                                <div class="message-attachment-name">${att.original_filename}</div>
                                <div class="message-attachment-meta">${formatFileSize(att.file_size)} • ${att.mime_type}</div>
                            </div>
                        </a>
                    </div>
                `;
            }
        }
        html += '</div>';
        return html;
    }

    // Attach file button click handler
    attachFileBtn.addEventListener('click', () => {
        fileInput.click();
    });

    // File input change handler
    fileInput.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            await uploadFiles(files);
        }
    });

    // ==================== End File Attachment Handling ====================

    // ==================== Vision Toggle for Local Models ====================

    // Function to check if current model is a local model
    function isLocalModel() {
        return currentProvider === 'lm_studio' || currentProvider === 'ollama';
    }

    // Function to update vision toggle button visibility and state
    function updateVisionToggleButton() {
        if (!visionToggleBtn) return;

        if (isLocalModel()) {
            visionToggleBtn.style.display = 'flex';
            updateVisionToggleState();
        } else {
            visionToggleBtn.style.display = 'none';
        }
    }

    // Function to update vision toggle button state (icon and class)
    function updateVisionToggleState() {
        if (!visionToggleBtn) return;

        const icon = visionToggleBtn.querySelector('i');
        if (localVisionEnabled) {
            visionToggleBtn.classList.add('active');
            visionToggleBtn.title = 'Vision enabled - click to disable';
            if (icon) {
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        } else {
            visionToggleBtn.classList.remove('active');
            visionToggleBtn.title = 'Vision disabled - click to enable';
            if (icon) {
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            }
        }
    }

    // Vision toggle button click handler
    if (visionToggleBtn) {
        visionToggleBtn.addEventListener('click', () => {
            localVisionEnabled = !localVisionEnabled;
            localStorage.setItem('localVisionEnabled', localVisionEnabled.toString());
            updateVisionToggleState();
        });
    }

    // ==================== End Vision Toggle ====================

    // ==================== Mobile Landscape Rotation Prompt ====================

    const rotationPrompt = document.getElementById('rotation-prompt');

    /**
     * Check if the device is a mobile device based on touch capability and screen size
     */
    function isMobileDevice() {
        // Check for touch capability and reasonable mobile screen size
        const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        const smallScreen = Math.min(window.screen.width, window.screen.height) <= 915;
        return hasTouch && smallScreen;
    }

    /**
     * Check if the device is in landscape orientation
     */
    function isLandscapeOrientation() {
        // Use screen.orientation API if available (more reliable)
        if (screen.orientation && screen.orientation.type) {
            return screen.orientation.type.includes('landscape');
        }
        // Fallback: compare window dimensions
        return window.innerWidth > window.innerHeight;
    }

    /**
     * Update the rotation prompt visibility based on device and orientation
     */
    function updateRotationPrompt() {
        if (!rotationPrompt) return;

        const shouldShow = isMobileDevice() && isLandscapeOrientation();

        if (shouldShow) {
            rotationPrompt.style.display = 'flex';
            mainContainer.style.display = 'none';
        } else {
            rotationPrompt.style.display = 'none';
            mainContainer.style.display = '';
        }
    }

    // Listen for orientation changes using the modern API
    if (screen.orientation) {
        screen.orientation.addEventListener('change', updateRotationPrompt);
    }

    // Fallback: listen for window resize events (orientation change triggers resize)
    window.addEventListener('resize', updateRotationPrompt);

    // Also listen for the legacy orientationchange event for older browsers
    window.addEventListener('orientationchange', () => {
        // Small delay to let the browser update dimensions
        setTimeout(updateRotationPrompt, 100);
    });

    // Initial check on page load
    updateRotationPrompt();

    // ==================== End Mobile Landscape Rotation Prompt ====================

    // Function to close all sidebars
    function closeAllSidebars() {
        sidebar.classList.remove('open');
        mainContainer.classList.remove('sidebar-open');
        sidebarOverlay.classList.remove('active');
    }

    // Function to check if we're in mobile view
    function isMobileView() {
        return window.innerWidth <= 768 || (window.innerWidth <= 915 && window.matchMedia('(orientation: landscape)').matches);
    }

    // Toggle left sidebar
    menuBtn.addEventListener('click', () => {
        const wasOpen = sidebar.classList.contains('open');
        closeAllSidebars();
        if (!wasOpen) {
            sidebar.classList.add('open');
            mainContainer.classList.add('sidebar-open');
            // Show overlay on all screen sizes for consistent behavior
            sidebarOverlay.classList.add('active');
        }
    });

    closeSidebarBtn.addEventListener('click', () => {
        closeAllSidebars();
    });

    // Tap outside to close sidebars
    sidebarOverlay.addEventListener('click', () => {
        closeAllSidebars();
    });

    // Maintain overlay state when sidebar is open on resize
    window.addEventListener('resize', () => {
        if (sidebar.classList.contains('open')) {
            sidebarOverlay.classList.add('active');
        } else {
            sidebarOverlay.classList.remove('active');
        }
    });


    // Helper function to update model ID display (header and input area)
    function updateModelIdDisplay(model, provider) {
        if (!window.MODEL_IDS) return;

        let modelId = '';
        if (provider === 'api') {
            // API providers use their model key directly
            modelId = window.MODEL_IDS[model] || '';
        } else {
            // Local providers (lm_studio, ollama)
            modelId = window.MODEL_IDS[provider] || '';
        }

        // Update header model ID display
        if (loadedModelId) {
            if (modelId) {
                loadedModelId.textContent = modelId;
                loadedModelId.style.display = 'block';
            } else {
                loadedModelId.style.display = 'none';
            }
        }

        // Update input area model ID display
        const inputModelIdDisplay = document.getElementById('input-model-id-display');
        const inputModelIdValue = document.getElementById('input-model-id-value');
        if (inputModelIdDisplay && inputModelIdValue) {
            if (modelId) {
                inputModelIdValue.textContent = modelId;
                inputModelIdDisplay.style.display = 'flex';
            } else {
                inputModelIdDisplay.style.display = 'none';
            }
        }
    }

    // Model selection
    const modelItems = document.querySelectorAll('.model-item');
    modelItems.forEach(item => {
        item.addEventListener('click', () => {
            // Remove active class from all items
            modelItems.forEach(i => i.classList.remove('active'));

            // Add active class to clicked item
            item.classList.add('active');

            // Get model and provider data
            currentModel = item.dataset.model;
            currentProvider = item.dataset.provider;

            // Save selected model to localStorage
            localStorage.setItem('selectedModel', currentModel);
            localStorage.setItem('selectedProvider', currentProvider);

            // Update header display
            const modelName = item.querySelector('span:not(.model-badge)').textContent;
            currentModelDisplay.textContent = modelName;

            // Update header icon
            const modelKey = currentProvider === 'api' ? currentModel : `simply_${currentProvider}`;
            if (modelIcons[modelKey]) {
                currentModelIcon.src = modelIcons[modelKey];
                currentModelIcon.style.display = 'block';
                // Add icon-specific classes for dark mode inversion
                currentModelIcon.classList.remove('chatgpt-header-icon', 'grok-header-icon');
                if (currentModel === 'openai') {
                    currentModelIcon.classList.add('chatgpt-header-icon');
                } else if (currentModel === 'xai') {
                    currentModelIcon.classList.add('grok-header-icon');
                }
            }

            // Update model ID display
            updateModelIdDisplay(currentModel, currentProvider);

            // Close right sidebar after model selection
            rightSidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    });

    // Initialize model selection from localStorage
    function initializeModelSelection() {
        const savedModel = localStorage.getItem('selectedModel');
        const savedProvider = localStorage.getItem('selectedProvider');

        if (savedModel && savedProvider) {
            // Set current model and provider
            currentModel = savedModel;
            currentProvider = savedProvider;

            // Get header dropdown items
            const headerModelItems = document.querySelectorAll('.header-model-item');

            // Find and activate the saved model item
            headerModelItems.forEach(item => {
                if (item.dataset.model === savedModel && item.dataset.provider === savedProvider) {
                    item.classList.add('active');

                    // Update header display
                    const modelName = item.querySelector('span:not(.model-badge)').textContent;
                    currentModelDisplay.textContent = modelName;

                    // Update header icon
                    const modelKey = savedProvider === 'api' ? savedModel : `simply_${savedProvider}`;
                    if (modelIcons[modelKey]) {
                        currentModelIcon.src = modelIcons[modelKey];
                        currentModelIcon.style.display = 'block';
                        // Add icon-specific classes for dark mode inversion
                        currentModelIcon.classList.remove('chatgpt-header-icon', 'grok-header-icon');
                        if (savedModel === 'openai') {
                            currentModelIcon.classList.add('chatgpt-header-icon');
                        } else if (savedModel === 'xai') {
                            currentModelIcon.classList.add('grok-header-icon');
                        }
                    }
                }
            });

            // Also sync with sidebar model items if they exist
            modelItems.forEach(item => {
                if (item.dataset.model === savedModel && item.dataset.provider === savedProvider) {
                    item.classList.add('active');
                }
            });

            // Update model ID display
            updateModelIdDisplay(savedModel, savedProvider);

            // Update vision toggle button visibility
            updateVisionToggleButton();
        } else {
            // No saved model, hide icon and model ID
            currentModelIcon.style.display = 'none';
            if (loadedModelId) loadedModelId.style.display = 'none';
            // Also hide input area model ID display
            const inputModelIdDisplay = document.getElementById('input-model-id-display');
            if (inputModelIdDisplay) inputModelIdDisplay.style.display = 'none';
        }
    }

    // Load enabled models and filter the model list
    async function loadEnabledModels() {
        try {
            const response = await fetch('/api/models/enabled');

            // Check for session expiration
            if (await handleSessionExpiration(response)) {
                return;
            }

            if (!response.ok) {
                console.warn('Failed to load enabled models, showing all models');
                return;
            }

            const data = await response.json();

            if (data.status === 'success' && data.models) {
                filterModelsByVisibility(data.models);
            }
        } catch (error) {
            console.error('Error loading enabled models:', error);
            // On error, show all models (fail open)
        }
    }

    // Filter model items based on visibility settings
    function filterModelsByVisibility(enabledModels) {
        const enabledProviders = new Set(enabledModels.map(m => m.provider));
        const sidebarModelItems = document.querySelectorAll('.model-item');
        const headerModelItems = document.querySelectorAll('.header-model-item');

        // Filter sidebar model items
        sidebarModelItems.forEach(item => {
            const modelProvider = item.dataset.model;
            const provider = item.dataset.provider;

            // Map the data-model attribute to the provider name used in the database
            let providerKey = modelProvider;

            // Handle special cases for local models
            if (modelProvider === 'simply') {
                if (provider === 'lm_studio') {
                    providerKey = 'simply_lm_studio';
                } else if (provider === 'ollama') {
                    providerKey = 'simply_ollama';
                }
            }

            // Show or hide based on enabled status
            if (enabledProviders.has(providerKey)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';

                // If this was the active model and it's now disabled, clear selection
                if (item.classList.contains('active')) {
                    item.classList.remove('active');
                    currentModel = null;
                    currentProvider = null;
                    localStorage.removeItem('selectedModel');
                    localStorage.removeItem('selectedProvider');
                    currentModelDisplay.textContent = 'Select Chat Model';
                    currentModelIcon.style.display = 'none';
                    // Also hide model ID displays
                    if (loadedModelId) loadedModelId.style.display = 'none';
                    const inputModelIdDisplay = document.getElementById('input-model-id-display');
                    if (inputModelIdDisplay) inputModelIdDisplay.style.display = 'none';
                }
            }
        });

        // Filter header dropdown model items
        headerModelItems.forEach(item => {
            const modelProvider = item.dataset.model;
            const provider = item.dataset.provider;

            // Map the data-model attribute to the provider name used in the database
            let providerKey = modelProvider;

            // Handle special cases for local models
            if (modelProvider === 'simply') {
                if (provider === 'lm_studio') {
                    providerKey = 'simply_lm_studio';
                } else if (provider === 'ollama') {
                    providerKey = 'simply_ollama';
                }
            }

            // Show or hide based on enabled status
            if (enabledProviders.has(providerKey)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';

                // If this was the active model and it's now disabled, clear selection
                if (item.classList.contains('active')) {
                    item.classList.remove('active');
                }
            }
        });
    }

    // Call initialization
    loadEnabledModels();
    initializeModelSelection();

    // Header model dropdown functionality
    const modelSelectorHeader = document.getElementById('model-selector-header');
    const headerModelDropdown = document.getElementById('header-model-dropdown');
    const headerModelItems = document.querySelectorAll('.header-model-item');

    // Toggle dropdown on header click
    if (modelSelectorHeader && headerModelDropdown) {
        modelSelectorHeader.addEventListener('click', (e) => {
            // Don't toggle if clicking on a model item
            if (e.target.closest('.header-model-item')) return;

            const isShown = headerModelDropdown.classList.contains('show');
            if (isShown) {
                headerModelDropdown.classList.remove('show');
                modelSelectorHeader.classList.remove('active');
            } else {
                headerModelDropdown.classList.add('show');
                modelSelectorHeader.classList.add('active');
            }
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (headerModelDropdown && modelSelectorHeader) {
            if (!modelSelectorHeader.contains(e.target)) {
                headerModelDropdown.classList.remove('show');
                modelSelectorHeader.classList.remove('active');
            }
        }
    });

    // Header model item selection
    headerModelItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.stopPropagation();

            // Store previous model and provider to detect changes
            const previousModel = currentModel;
            const previousProvider = currentProvider;

            // Remove active class from all header items
            headerModelItems.forEach(i => i.classList.remove('active'));

            // Add active class to clicked item
            item.classList.add('active');

            // Get model and provider data
            const newModel = item.dataset.model;
            const newProvider = item.dataset.provider;

            // Check if model actually changed (not just re-selecting the same model)
            const modelChanged = (previousModel !== null && previousProvider !== null) &&
                                (previousModel !== newModel || previousProvider !== newProvider);

            // Update current model and provider
            currentModel = newModel;
            currentProvider = newProvider;

            // Save selected model to localStorage
            localStorage.setItem('selectedModel', currentModel);
            localStorage.setItem('selectedProvider', currentProvider);

            // Update header display
            const modelName = item.querySelector('span:not(.model-badge)').textContent;
            currentModelDisplay.textContent = modelName;

            // Update header icon
                const modelKey = currentProvider === 'api' ? currentModel : `simply_${currentProvider}`;
                if (modelIcons[modelKey]) {
                    currentModelIcon.src = modelIcons[modelKey];
                    currentModelIcon.style.display = 'block';
                    // Add icon-specific classes for dark mode inversion
                    currentModelIcon.classList.remove('chatgpt-header-icon', 'grok-header-icon');
                    if (currentModel === 'openai') {
                        currentModelIcon.classList.add('chatgpt-header-icon');
                    } else if (currentModel === 'xai') {
                        currentModelIcon.classList.add('grok-header-icon');
                    }
                }

                // Update model ID display
                updateModelIdDisplay(currentModel, currentProvider);

            // Also update the sidebar model items to stay in sync
            modelItems.forEach(sidebarItem => {
                if (sidebarItem.dataset.model === currentModel && sidebarItem.dataset.provider === currentProvider) {
                    sidebarItem.classList.add('active');
                } else {
                    sidebarItem.classList.remove('active');
                }
            });

            // If model changed, automatically start a new chat to prevent contamination
            if (modelChanged) {
                // Clear current session
                currentSessionId = null;
                localStorage.removeItem('session_id');

                // Clear chat messages
                chatMessages.innerHTML = '';

                // Clear any pending attachments
                clearAttachments();

                // Ensure welcome message is shown
                ensureWelcomeMessage();
                toggleWelcomeMessage();

                // Stop any ongoing generation
                if (isBotTyping) {
                    setBotTyping(false);
                }

                // Refresh session list to deselect previous session
                loadSessions();

                // Scroll to top to show welcome message
                chatMessages.scrollTop = 0;
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }

            // Update vision toggle button visibility
            updateVisionToggleButton();

            // Close dropdown after selection
            headerModelDropdown.classList.remove('show');
            modelSelectorHeader.classList.remove('active');
        });
    });

    // Settings button - redirect to settings page
    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            window.location.href = '/auth/settings';
        });
    }

    // Profile button
    if (profileBtn) {
        profileBtn.addEventListener('click', () => {
            window.location.href = '/auth/profile';
        });
    }

    // Logout button
    if (logoutBtnSidebar) {
        logoutBtnSidebar.addEventListener('click', async () => {
            try {
                const response = await fetch('/auth/logout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (response.ok) {
                    // Clear session storage
                    localStorage.removeItem('session_id');
                    // Redirect to login page
                    window.location.href = '/auth/login';
                } else {
                    console.error('Logout failed');
                    alert('Logout failed. Please try again.');
                }
            } catch (error) {
                console.error('Error during logout:', error);
                alert('An error occurred during logout.');
            }
        });
    }

    // Chat History Collapse/Expand functionality
    const chatHistoryHeader = document.getElementById('chat-history-header');
    const sessionListContainer = document.getElementById('session-list');

    // Check if chat history should be collapsed (from localStorage)
    const isChatHistoryCollapsed = localStorage.getItem('chatHistoryCollapsed') === 'true';
    if (isChatHistoryCollapsed) {
        chatHistoryHeader.classList.add('collapsed');
        sessionListContainer.classList.add('collapsed');
    }

    // Toggle chat history on header click
    chatHistoryHeader.addEventListener('click', () => {
        const isCollapsed = chatHistoryHeader.classList.toggle('collapsed');
        sessionListContainer.classList.toggle('collapsed');

        // Save state to localStorage
        localStorage.setItem('chatHistoryCollapsed', isCollapsed);
    });

    // Load sessions on page load
    loadSessions();

    if (currentSessionId) {
        loadChatHistory(currentSessionId);
    }

    const saveConfirmationModal = document.getElementById('save-confirmation-modal');
    const okBtn = document.getElementById('ok-btn');

    okBtn.addEventListener('click', () => {
        saveConfirmationModal.style.display = 'none';
    });

    // Auto-resize textarea function
    function autoResizeTextarea() {
        chatInput.style.height = 'auto'; // Reset height to recalculate
        const newHeight = Math.min(chatInput.scrollHeight, 200); // Max 200px
        chatInput.style.height = newHeight + 'px';
    }

    // Reset textarea height
    function resetTextareaHeight() {
        chatInput.style.height = 'auto';
    }

    // Auto-resize on input
    chatInput.addEventListener('input', autoResizeTextarea);

    // Send message or stop generation
    sendBtn.addEventListener('click', () => {
        if (isBotTyping) {
            stopGeneration();
            } else {
                sendMessage();
        }
    });
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
                sendMessage();
        }
    });

    // ==================== Improve Prompt Feature ====================

    const improvePromptBtn = document.getElementById('improve-prompt-btn');
    const improvePromptModal = document.getElementById('improve-prompt-modal');
    const improvePromptCloseBtn = document.getElementById('improve-prompt-close-btn');
    const originalPromptInput = document.getElementById('original-prompt-input');
    const improvedPromptOutput = document.getElementById('improved-prompt-output');
    const generatePromptBtn = document.getElementById('generate-prompt-btn');
    const usePromptBtn = document.getElementById('use-prompt-btn');
    const cancelPromptBtn = document.getElementById('cancel-prompt-btn');

    // Open modal and populate with current chat input
    if (improvePromptBtn) {
        improvePromptBtn.addEventListener('click', () => {
            // Check if a model is selected
            if (!currentModel || !currentProvider) {
                alert('Please select a chat model first.');
                return;
            }

            // Populate original prompt with current chat input
            const currentText = chatInput.value.trim();
            originalPromptInput.value = currentText;
            improvedPromptOutput.value = '';
            usePromptBtn.disabled = true;

            // Show modal
            improvePromptModal.style.display = 'flex';

            // Focus on original prompt textarea
            setTimeout(() => originalPromptInput.focus(), 100);
        });
    }

    // Close modal function
    function closeImprovePromptModal() {
        improvePromptModal.style.display = 'none';
        originalPromptInput.value = '';
        improvedPromptOutput.value = '';
        usePromptBtn.disabled = true;

        // Reset generate button state
        generatePromptBtn.classList.remove('loading');
        generatePromptBtn.disabled = false;
        generatePromptBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i><span>Generate</span>';
    }

    // Close button handler
    if (improvePromptCloseBtn) {
        improvePromptCloseBtn.addEventListener('click', closeImprovePromptModal);
    }

    // Cancel button handler
    if (cancelPromptBtn) {
        cancelPromptBtn.addEventListener('click', closeImprovePromptModal);
    }

    // Close on overlay click (outside dialog)
    if (improvePromptModal) {
        improvePromptModal.addEventListener('click', (e) => {
            if (e.target === improvePromptModal) {
                closeImprovePromptModal();
            }
        });
    }

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && improvePromptModal && improvePromptModal.style.display === 'flex') {
            closeImprovePromptModal();
        }
    });

    // Generate improved prompt
    if (generatePromptBtn) {
        generatePromptBtn.addEventListener('click', async () => {
            const originalPrompt = originalPromptInput.value.trim();

            if (!originalPrompt) {
                alert('Please enter a prompt to improve.');
                originalPromptInput.focus();
                return;
            }

            // Set loading state
            generatePromptBtn.classList.add('loading');
            generatePromptBtn.disabled = true;
            generatePromptBtn.innerHTML = '<i class="fa-solid fa-spinner"></i><span>Generating...</span>';
            improvedPromptOutput.value = '';
            usePromptBtn.disabled = true;

            try {
                // Determine model to use
                let model = currentModel;
                let local_model_provider = '';

                if (currentModel === 'simply') {
                    local_model_provider = currentProvider;
                }

                const response = await fetch('/api/improve_prompt', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        prompt: originalPrompt,
                        model: model,
                        local_model_provider: local_model_provider
                    })
                });

                // Check for session expiration
                if (await handleSessionExpiration(response)) {
                    closeImprovePromptModal();
                    return;
                }

                const data = await response.json();

                if (response.ok && data.status === 'success') {
                    improvedPromptOutput.value = data.improved_prompt;
                    usePromptBtn.disabled = false;
                } else if (response.status === 429) {
                    alert('Rate limit exceeded. Please wait a moment before trying again.');
                } else {
                    alert(data.error || 'Failed to improve prompt. Please try again.');
                }

            } catch (error) {
                console.error('Error improving prompt:', error);
                alert('An error occurred while improving the prompt. Please try again.');
            } finally {
                // Reset button state
                generatePromptBtn.classList.remove('loading');
                generatePromptBtn.disabled = false;
                generatePromptBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i><span>Generate</span>';
            }
        });
    }

    // Use improved prompt
    if (usePromptBtn) {
        usePromptBtn.addEventListener('click', () => {
            const improvedPrompt = improvedPromptOutput.value.trim();

            if (improvedPrompt) {
                chatInput.value = improvedPrompt;

                // Trigger auto-resize of textarea
                autoResizeTextarea();

                // Close modal
                closeImprovePromptModal();

                // Focus chat input
                chatInput.focus();
            }
        });
    }

    // ==================== End Improve Prompt Feature ====================

    // Scroll to bottom button functionality
    function updateScrollToBottomButton() {
        if (!scrollToBottomBtn || !chatMessages) return;

        // Check if content is scrollable and not at bottom
        const isScrollable = chatMessages.scrollHeight > chatMessages.clientHeight;
        const isNearBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight < 100;

        if (isScrollable && !isNearBottom) {
            scrollToBottomBtn.style.display = 'flex';
        } else {
            scrollToBottomBtn.style.display = 'none';
        }
    }

    // Listen for scroll events on chat messages
    chatMessages.addEventListener('scroll', updateScrollToBottomButton);

    // Click handler for scroll to bottom button
    if (scrollToBottomBtn) {
        scrollToBottomBtn.addEventListener('click', () => {
            chatMessages.scrollTo({
                top: chatMessages.scrollHeight,
                behavior: 'smooth'
            });
        });
    }

    // Initial check for scroll button visibility
    updateScrollToBottomButton();

    async function sendMessage() {
        if (isBotTyping) return;
        const message = chatInput.value.trim();

        // Allow sending if either message or attachments are present
        if (!message && pendingAttachments.length === 0) return;

        // Check if a model is selected
        if (!currentModel || !currentProvider) {
            alert('Please select a chat model first from the menu.');
            return;
        }

        // Determine the model value to send to the backend
        let model = currentModel;
        let local_model_provider = '';

        // Handle local models
        if (currentModel === 'simply') {
            local_model_provider = currentProvider; // 'lm_studio' or 'ollama'
        }

        // Get attachments to send (remove file objects, keep metadata)
        const attachmentsToSend = pendingAttachments.map(att => ({
            original_filename: att.original_filename,
            stored_filename: att.stored_filename,
            file_path: att.file_path,
            file_type: att.file_type,
            mime_type: att.mime_type,
            file_size: att.file_size
        }));

        addMessage(message || 'See attached files', 'user', attachmentsToSend);
        chatInput.value = '';
        resetTextareaHeight(); // Reset textarea height after sending
        clearAttachments(); // Clear attachments after sending
        setBotTyping(true);

        // Show typing indicator while waiting for response
        typingIndicatorElement = showTypingIndicator();

        const modelToUse = currentModel === 'simply' ? local_model_provider : currentModel;

        try {
            // Create AbortController for this request
            currentAbortController = new AbortController();

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message,
                    model,
                    local_model_provider,
                    session_id: currentSessionId,
                    attachments: attachmentsToSend,
                    local_vision_enabled: localVisionEnabled
                }),
                signal: currentAbortController.signal
            });

            // Check for session expiration
            if (await handleSessionExpiration(response)) {
                setBotTyping(false);
                return;
            }

            if (!response.ok) {
                // Handle rate limit errors with a user-friendly message
                if (response.status === 429) {
                    throw new Error('Rate limit exceeded. Please wait a moment before sending more messages.');
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullContent = '';
            let botMessageContent = null; // Will be created when typing indicator is removed

            // Thinking bubble tracking
            let insideThinkingTags = false;
            let thinkingBuffer = '';
            let regularBuffer = '';
            let thinkingBubble = null;
            let thinkingContentDiv = null;

            // Helper function to remove typing indicator and create bot message
            function ensureBotMessageCreated() {
                if (!botMessageContent) {
                    // Remove typing indicator
                    if (typingIndicatorElement) {
                        typingIndicatorElement.remove();
                        typingIndicatorElement = null;
                    }
                    // Create empty bot message that will be filled with streaming content
                    botMessageContent = addMessage('', 'bot', null, null, modelToUse);
                }
            }

            // Helper function to create thinking bubble
            function createThinkingBubble() {
                const messageDiv = botMessageContent.closest('.message');
                const contentDiv = messageDiv.querySelector('.message-content');

                const bubble = document.createElement('div');
                // Start collapsed with thinking-in-progress animation
                bubble.className = 'thinking-bubble thinking-in-progress';
                bubble.innerHTML = `
                    <div class="thinking-header">
                        <span class="thinking-icon">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
                            </svg>
                        </span>
                        <span class="thinking-label">Thinking...</span>
                        <button class="thinking-toggle" aria-label="Toggle thinking content">
                            <svg class="chevron-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </button>
                    </div>
                    <div class="thinking-content" style="display: none;">
                    </div>
                `;

                // Insert thinking bubble before the actual content
                contentDiv.insertBefore(bubble, botMessageContent);

                // Add click handler
                const thinkingHeader = bubble.querySelector('.thinking-header');
                const thinkingContent = bubble.querySelector('.thinking-content');
                thinkingHeader.addEventListener('click', () => {
                    const isExpanded = thinkingContent.style.display === 'block';
                    thinkingContent.style.display = isExpanded ? 'none' : 'block';
                    bubble.classList.toggle('expanded', !isExpanded);
                });

                return { bubble, thinkingContent };
            }

            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process complete SSE messages (separated by \n\n)
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete message in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.type === 'session_id') {
                                // Update session ID if this is a new chat
                                // DON'T remove typing indicator yet - wait for actual content
                                if (!currentSessionId) {
                                    currentSessionId = data.session_id;
                                    localStorage.setItem('session_id', currentSessionId);
                                    loadSessions();
                                }
                            } else if (data.type === 'content') {
                                // Remove typing indicator and create bot message on first content
                                ensureBotMessageCreated();
                                // Append streaming content
                                fullContent += data.content;

                                // Process content to detect thinking tags
                                let content = data.content;
                                let remainingContent = content;

                                while (remainingContent.length > 0) {
                                    if (!insideThinkingTags) {
                                        // Check if thinking tag starts
                                        const thinkStartIndex = remainingContent.indexOf('<think>');

                                        if (thinkStartIndex !== -1) {
                                            // Add content before <think> to regular buffer
                                            if (thinkStartIndex > 0) {
                                                regularBuffer += remainingContent.substring(0, thinkStartIndex);
                                                botMessageContent.innerHTML = convertMarkdown(regularBuffer);
                                            }

                                            // Create thinking bubble if it doesn't exist
                                            if (!thinkingBubble) {
                                                const result = createThinkingBubble();
                                                thinkingBubble = result.bubble;
                                                thinkingContentDiv = result.thinkingContent;
                                            }

                                            insideThinkingTags = true;
                                            remainingContent = remainingContent.substring(thinkStartIndex + 7); // Skip <think>
                                        } else {
                                            // No thinking tag, add to regular content
                                            regularBuffer += remainingContent;
                                            botMessageContent.innerHTML = convertMarkdown(regularBuffer);
                                            remainingContent = '';
                                        }
                                    } else {
                                        // Inside thinking tags, check for closing tag
                                        const thinkEndIndex = remainingContent.indexOf('</think>');

                                        if (thinkEndIndex !== -1) {
                                            // Add content before </think> to thinking buffer
                                            thinkingBuffer += remainingContent.substring(0, thinkEndIndex);
                                            if (thinkingContentDiv) {
                                                thinkingContentDiv.innerHTML = convertMarkdown(thinkingBuffer);
                                            }

                                            insideThinkingTags = false;
                                            remainingContent = remainingContent.substring(thinkEndIndex + 8); // Skip </think>
                                        } else {
                                            // Still inside thinking, add to thinking buffer
                                            thinkingBuffer += remainingContent;
                                            if (thinkingContentDiv) {
                                                thinkingContentDiv.innerHTML = convertMarkdown(thinkingBuffer);
                                            }
                                            remainingContent = '';
                                        }
                                    }
                                }

                                // Auto-scroll to bottom
                                chatMessages.scrollTo({
                                    top: chatMessages.scrollHeight,
                                    behavior: 'smooth'
                                });
                            } else if (data.type === 'done') {
                                // Remove typing indicator if still present
                                ensureBotMessageCreated();

                                // Streaming complete - apply final formatting
                                fullContent = data.full_content || fullContent;

                                // Extract thinking content
                                const thinkingMatch = fullContent.match(/<think>(.*?)<\/think>/s);
                                const thinkingContent = thinkingMatch ? thinkingMatch[1].trim() : null;
                                const filteredResponse = fullContent.replace(/<think>.*?<\/think>/gs, '').trim();

                                // Update message with final content (use regularBuffer if populated during streaming)
                                if (regularBuffer) {
                                    botMessageContent.innerHTML = convertMarkdown(regularBuffer);
                                } else {
                                    botMessageContent.innerHTML = convertMarkdown(filteredResponse);
                                }

                                // If thinking bubble was created during streaming, finalize it
                                if (thinkingBubble) {
                                    // Remove the thinking-in-progress animation class
                                    thinkingBubble.classList.remove('thinking-in-progress');

                                    // Update label text from "Thinking..." to "Thinking"
                                    const thinkingLabel = thinkingBubble.querySelector('.thinking-label');
                                    if (thinkingLabel) {
                                        thinkingLabel.textContent = 'Thinking';
                                    }
                                }

                                // If there's thinking content and bubble wasn't created during streaming, create it now
                                if (thinkingContent && !thinkingBubble) {
                                    const messageDiv = botMessageContent.closest('.message');
                                    const contentDiv = messageDiv.querySelector('.message-content');

                                    // Create thinking bubble (collapsed by default when not streamed)
                                    const bubble = document.createElement('div');
                                    bubble.className = 'thinking-bubble';
                                    bubble.innerHTML = `
                                        <div class="thinking-header">
                                            <span class="thinking-icon">
                                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                                    <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
                                                </svg>
                                            </span>
                                            <span class="thinking-label">Thinking</span>
                                            <button class="thinking-toggle" aria-label="Toggle thinking content">
                                                <svg class="chevron-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                                    <polyline points="6 9 12 15 18 9"></polyline>
                                                </svg>
                                            </button>
                                        </div>
                                        <div class="thinking-content" style="display: none;">
                                            ${convertMarkdown(thinkingContent)}
                                        </div>
                                    `;

                                    // Insert thinking bubble before the actual content
                                    contentDiv.insertBefore(bubble, botMessageContent);

                                    // Add click handler
                                    const thinkingHeader = bubble.querySelector('.thinking-header');
                                    const thinkingContentDivFinal = bubble.querySelector('.thinking-content');
                                    thinkingHeader.addEventListener('click', () => {
                                        const isExpanded = thinkingContentDivFinal.style.display === 'block';
                                        thinkingContentDivFinal.style.display = isExpanded ? 'none' : 'block';
                                        bubble.classList.toggle('expanded', !isExpanded);
                                    });

                                    thinkingBubble = bubble;
                                    thinkingContentDiv = thinkingContentDivFinal;
                                }

                                // Apply syntax highlighting and copy buttons to regular content
                                botMessageContent.querySelectorAll('pre code').forEach((block) => {
                                    if (window.Prism) {
                                        Prism.highlightElement(block);
                                    }
                                });
                                addCopyButtons(botMessageContent);

                                // Apply syntax highlighting to thinking content if it exists
                                if (thinkingContentDiv) {
                                    thinkingContentDiv.querySelectorAll('pre code').forEach((block) => {
                                        if (window.Prism) {
                                            Prism.highlightElement(block);
                                        }
                                    });
                                    addCopyButtons(thinkingContentDiv);
                                    renderMath(thinkingContentDiv);
                                }

                                // Render math expressions in regular content
                                renderMath(botMessageContent);

                                setBotTyping(false);
                            } else if (data.type === 'error') {
                                // Remove typing indicator and create bot message for error
                                ensureBotMessageCreated();

                                // Display error
                                botMessageContent.innerHTML = `<span class="error-message">Error: ${data.content}</span>`;
                                setBotTyping(false);
                            } else if (data.type === 'user_message_id') {
                                // Add delete button and token display to the last user message
                                const userMsgs = chatMessages.querySelectorAll('.message.user');
                                if (userMsgs.length > 0) {
                                    const lastUserMsg = userMsgs[userMsgs.length - 1];
                                    lastUserMsg.setAttribute('data-message-id', data.message_id);
                                    addDeleteButtonToMessage(lastUserMsg, data.message_id);
                                    // Add token display if available
                                    if (data.input_tokens && data.input_tokens > 0) {
                                        addTokenDisplayToMessage(lastUserMsg, data.input_tokens, 'input', data.tokens_estimated);
                                    }
                                }
                            } else if (data.type === 'bot_message_id') {
                                // Add delete button and token display to the last bot message
                                const botMsgs = chatMessages.querySelectorAll('.message.bot');
                                if (botMsgs.length > 0) {
                                    const lastBotMsg = botMsgs[botMsgs.length - 1];
                                    lastBotMsg.setAttribute('data-message-id', data.message_id);
                                    addDeleteButtonToMessage(lastBotMsg, data.message_id);
                                    // Add token display if available
                                    if (data.output_tokens && data.output_tokens > 0) {
                                        addTokenDisplayToMessage(lastBotMsg, data.output_tokens, 'output', data.tokens_estimated);
                                    }
                                    // Update total tokens counter
                                    updateTotalTokensDisplay();
                                }
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
            }

        } catch (error) {
            // Remove typing indicator if still present
            if (typingIndicatorElement) {
                typingIndicatorElement.remove();
                typingIndicatorElement = null;
            }

            // Create bot message if not already created
            if (!botMessageContent) {
                botMessageContent = addMessage('', 'bot', null, null, modelToUse);
            }

            // Handle user-initiated abort gracefully
            if (error.name === 'AbortError') {
                console.log('Generation stopped by user');
                // Keep whatever content was already streamed
                if (botMessageContent.innerHTML.trim() === '') {
                    botMessageContent.innerHTML = '<span class="stopped-message"><i>Generation stopped</i></span>';
                }
            } else {
                console.error('Error fetching chat response:', error);
                botMessageContent.innerHTML = `<span class="error-message">Error: Could not get a response from the server. ${error.message}</span>`;
            }
            setBotTyping(false);
        }
    }

    function setBotTyping(isTyping) {
        isBotTyping = isTyping;
        chatInput.disabled = isTyping;

        // Toggle between send and stop button
        if (isTyping) {
            sendBtn.innerHTML = '<i class="fa-solid fa-stop"></i>';
            sendBtn.title = 'Stop generating';
            sendBtn.classList.add('stop-btn');
            sendBtn.classList.remove('disabled');
            sendBtn.disabled = false;
        } else {
            sendBtn.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
            sendBtn.title = 'Send message';
            sendBtn.classList.remove('stop-btn');
            currentAbortController = null;
        }
    }

    function stopGeneration() {
        if (currentAbortController) {
            currentAbortController.abort();
            currentAbortController = null;
        }

        // Remove typing indicator if present
        if (typingIndicatorElement) {
            typingIndicatorElement.remove();
            typingIndicatorElement = null;
        }

        setBotTyping(false);
    }

    // Helper function to format timestamp with date and time in user's local timezone
    function formatTimestamp(timestamp) {
        const date = timestamp ? new Date(timestamp) : new Date();

        // Get date components in local timezone
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');

        return `${year}/${month}/${day} ${hours}:${minutes}`;
    }

    // Delete a message from the chat
    async function deleteMessage(messageId, messageElement) {
        if (!confirm('Delete this message? It will no longer be used as context for follow-up questions.')) {
            return;
        }

        try {
            const response = await fetch(`/api/messages/${messageId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });

            // Check for session expiration
            if (await handleSessionExpiration(response)) {
                return;
            }

            if (response.ok) {
                messageElement.remove();
            } else {
                const data = await response.json();
                alert('Failed to delete: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Delete error:', error);
            alert('Failed to delete message');
        }
    }

    // Add delete button to an existing message (used when message ID is received after creation)
    function addDeleteButtonToMessage(messageDiv, messageId) {
        const footer = messageDiv.querySelector('.message-footer');
        if (footer && !footer.querySelector('.message-delete-btn')) {
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'message-delete-btn';
            deleteBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>`;
            deleteBtn.title = 'Delete message';
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                deleteMessage(messageId, messageDiv);
            };
            footer.appendChild(deleteBtn);
        }
    }

    // Add token display to an existing message (used when token data is received after creation)
    function addTokenDisplayToMessage(messageDiv, tokenCount, tokenType, estimated) {
        const footer = messageDiv.querySelector('.message-footer');
        if (footer && !footer.querySelector('.message-tokens') && tokenCount > 0) {
            const tokenDiv = document.createElement('div');
            tokenDiv.className = 'message-tokens';
            const estimatedPrefix = estimated ? '~' : '';
            // Both input and output use 'tokens' as the label
            const displayLabel = 'tokens';
            tokenDiv.innerHTML = `
                <span class="token-count">${estimatedPrefix}${tokenCount.toLocaleString()}</span>
                <span class="token-label">${displayLabel}</span>
            `;
            // Insert at the beginning of footer (before timestamp)
            footer.insertBefore(tokenDiv, footer.firstChild);
        }
    }

    // Update the total tokens display in the input section
    function updateTotalTokensDisplay() {
        const totalTokensDisplay = document.getElementById('total-tokens-display');
        const totalTokensValue = document.getElementById('total-tokens-value');

        if (!totalTokensDisplay || !totalTokensValue) return;

        // Sum all token counts from messages
        let total = 0;
        chatMessages.querySelectorAll('.message-tokens .token-count').forEach(el => {
            // Remove all non-digit characters (handles ~, commas, spaces, dots as thousands separators)
            const text = el.textContent.replace(/\D/g, '');
            const count = parseInt(text) || 0;
            total += count;
        });

        totalTokensValue.textContent = total.toLocaleString();
        totalTokensDisplay.style.display = total > 0 ? 'flex' : 'none';
    }

    // Reset total tokens display (called on new chat)
    function resetTotalTokensDisplay() {
        const totalTokensDisplay = document.getElementById('total-tokens-display');
        const totalTokensValue = document.getElementById('total-tokens-value');

        if (totalTokensDisplay) {
            totalTokensDisplay.style.display = 'none';
        }
        if (totalTokensValue) {
            totalTokensValue.textContent = '0';
        }
    }

    function addMessage(content, type, attachments, timestamp, modelUsed, thinkingContent, messageId = null, tokenCount = null, tokensEstimated = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;

        // Store messageId on the element for deletion functionality
        if (messageId) {
            messageDiv.setAttribute('data-message-id', messageId);
        }

        // Create name tag (only for bot messages)
        let nameTagDiv = null;
        if (type === 'bot') {
            nameTagDiv = document.createElement('div');
            nameTagDiv.className = 'message-name-tag';
            const currentModel = modelUsed || getCurrentModel();
            const modelInfo = getModelInfo(currentModel);
            nameTagDiv.innerHTML = `
                <img src="${modelInfo.logo}" alt="${modelInfo.name}" class="name-tag-logo">
                <span class="name-tag-text">${modelInfo.name}</span>
            `;
        }

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        // Add thinking bubble if present (only for bot messages)
        if (type === 'bot' && thinkingContent) {
            const thinkingBubble = document.createElement('div');
            thinkingBubble.className = 'thinking-bubble';
            thinkingBubble.innerHTML = `
                <div class="thinking-header">
                    <span class="thinking-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
                        </svg>
                    </span>
                    <span class="thinking-label">Thinking</span>
                    <button class="thinking-toggle" aria-label="Toggle thinking content">
                        <svg class="chevron-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                </div>
                <div class="thinking-content" style="display: none;">
                    ${convertMarkdown(thinkingContent)}
                </div>
            `;
            contentDiv.appendChild(thinkingBubble);

            // Add click handler for toggle - entire header is clickable
            const thinkingHeader = thinkingBubble.querySelector('.thinking-header');
            const thinkingContentDiv = thinkingBubble.querySelector('.thinking-content');
            thinkingHeader.addEventListener('click', () => {
                const isExpanded = thinkingContentDiv.style.display === 'block';
                thinkingContentDiv.style.display = isExpanded ? 'none' : 'block';
                thinkingBubble.classList.toggle('expanded', !isExpanded);
            });
        }

        // Create a wrapper for the actual message content (for streaming compatibility)
        const actualContentWrapper = document.createElement('div');
        actualContentWrapper.className = 'actual-content-wrapper';

        if (content) {
            actualContentWrapper.innerHTML = convertMarkdown(content);

            // For bot messages, apply syntax highlighting and add copy buttons
            if (type === 'bot') {
                actualContentWrapper.querySelectorAll('pre code').forEach((block) => {
                    if (window.Prism) {
                        Prism.highlightElement(block);
                    }
                });
                addCopyButtons(actualContentWrapper);
            }

            // Render math expressions after content is added
            renderMath(actualContentWrapper);
        }

        // Add attachments if present
        if (attachments && attachments.length > 0) {
            actualContentWrapper.innerHTML += renderAttachmentsInMessage(attachments, type);
        }

        contentDiv.appendChild(actualContentWrapper);

        // Create message footer with tokens, timestamp and delete button
        const footerDiv = document.createElement('div');
        footerDiv.className = 'message-footer';

        // Add token display if tokenCount is available and > 0
        if (tokenCount && tokenCount > 0) {
            const tokenDiv = document.createElement('div');
            tokenDiv.className = 'message-tokens';
            const tokenLabel = 'tokens';
            const estimatedPrefix = tokensEstimated ? '~' : '';
            tokenDiv.innerHTML = `
                <span class="token-count">${estimatedPrefix}${tokenCount.toLocaleString()}</span>
                <span class="token-label">${tokenLabel}</span>
            `;
            footerDiv.appendChild(tokenDiv);
        }

        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'timestamp';
        timestampDiv.textContent = formatTimestamp(timestamp);
        footerDiv.appendChild(timestampDiv);

        // Add delete button if we have a messageId
        if (messageId) {
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'message-delete-btn';
            deleteBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>`;
            deleteBtn.title = 'Delete message';
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                deleteMessage(messageId, messageDiv);
            };
            footerDiv.appendChild(deleteBtn);
        }

        if (nameTagDiv) {
            messageDiv.appendChild(nameTagDiv);
        }
        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(footerDiv);
        chatMessages.appendChild(messageDiv);

        // Hide welcome message when first message is added
        toggleWelcomeMessage();

        chatMessages.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: 'smooth'
        });

        return actualContentWrapper;
    }

    // Helper function to get current model
    function getCurrentModel() {
        const modelSelect = document.getElementById('model-select');
        const localProviderSelect = document.getElementById('local-model-provider-select');

        if (modelSelect && modelSelect.value === 'local' && localProviderSelect) {
            return localProviderSelect.value;
        }
        return modelSelect ? modelSelect.value : 'gemini';
    }

    // Helper function to get model information
    function getModelInfo(model) {
        const modelData = {
            'gemini': {
                name: 'Gemini',
                logo: '/static/images/gemini.png'
            },
            'xai': {
                name: 'Grok',
                logo: '/static/images/grok.png'
            },
            'openai': {
                name: 'ChatGPT',
                logo: '/static/images/chatgpt.png'
            },
            'anthropic': {
                name: 'Claude',
                logo: '/static/images/claude.png'
            },
            'lm_studio': {
                name: 'LM Studio',
                logo: '/static/images/lmstudio.png'
            },
            'ollama': {
                name: 'Ollama',
                logo: '/static/images/ollama.png'
            }
        };

        return modelData[model] || modelData['gemini'];
    }

    // Helper function to map model_used to model and provider format
    function mapModelUsedToSelection(modelUsed) {
        if (!modelUsed) return null;

        // Map model_used values to the format used by the dropdown
        const modelMapping = {
            'gemini': { model: 'gemini', provider: 'api' },
            'xai': { model: 'xai', provider: 'api' },
            'openai': { model: 'openai', provider: 'api' },
            'anthropic': { model: 'anthropic', provider: 'api' },
            'lm_studio': { model: 'simply', provider: 'lm_studio' },
            'ollama': { model: 'simply', provider: 'ollama' }
        };

        return modelMapping[modelUsed] || null;
    }

    // Helper function to update model selection UI
    function updateModelSelectionUI(model, provider) {
        if (!model || !provider) return;

        // Update current model and provider
        currentModel = model;
        currentProvider = provider;

        // Save to localStorage
        localStorage.setItem('selectedModel', model);
        localStorage.setItem('selectedProvider', provider);

        // Get model info for display
        const modelKey = provider === 'api' ? model : `simply_${provider}`;
        const modelInfo = getModelInfo(provider === 'api' ? model : provider);

        // Update header display
        currentModelDisplay.textContent = modelInfo.name;

        // Update header icon
        if (modelIcons[modelKey]) {
            currentModelIcon.src = modelIcons[modelKey];
            currentModelIcon.style.display = 'block';
            // Add icon-specific classes for dark mode inversion
            currentModelIcon.classList.remove('chatgpt-header-icon', 'grok-header-icon');
            if (model === 'openai') {
                currentModelIcon.classList.add('chatgpt-header-icon');
            } else if (model === 'xai') {
                currentModelIcon.classList.add('grok-header-icon');
            }
        }

        // Update model ID display
        updateModelIdDisplay(model, provider);

        // Update active state in header dropdown
        headerModelItems.forEach(item => {
            if (item.dataset.model === model && item.dataset.provider === provider) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // Update active state in sidebar model items
        modelItems.forEach(item => {
            if (item.dataset.model === model && item.dataset.provider === provider) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // Update vision toggle button visibility
        updateVisionToggleButton();
    }

    function showTypingIndicator() {
        // Get current model info for name tag
        const currentModelForIndicator = currentModel === 'simply' ?
            (currentProvider === 'lm_studio' ? 'lm_studio' : 'ollama') :
            currentModel;
        const modelInfo = getModelInfo(currentModelForIndicator);

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot typing-indicator';

        // Create name tag
        const nameTagDiv = document.createElement('div');
        nameTagDiv.className = 'message-name-tag';
        nameTagDiv.innerHTML = `
            <img src="${modelInfo.logo}" alt="${modelInfo.name}" class="name-tag-logo">
            <span class="name-tag-text">${modelInfo.name}</span>
        `;

        // Create content with typing dots
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = '<div class="dot-flashing"></div>';

        // Create timestamp (empty for typing indicator)
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'timestamp';
        timestampDiv.textContent = formatTimestamp();

        // Assemble message
        messageDiv.appendChild(nameTagDiv);
        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timestampDiv);

        chatMessages.appendChild(messageDiv);

        // Hide welcome message when typing indicator appears
        toggleWelcomeMessage();

        chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
        return messageDiv;
    }

    function convertMarkdown(text) {
        // === COMPREHENSIVE LATEX PREPROCESSING ===
        // This section handles all common LaTeX delimiter formats from different AI models

        // 1. Protect code blocks from LaTeX processing
        const codeBlocks = [];
        text = text.replace(/(```[\s\S]*?```|`[^`]+`)/g, (match, code) => {
            codeBlocks.push(code);
            return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
        });

        // 2. Convert \[ \] display math to $$ $$
        text = text.replace(/\\\[([\s\S]*?)\\\]/g, (match, latex) => {
            return '\n$$' + latex.trim() + '$$\n';
        });

        // 3. Convert \( \) inline math to $ $
        text = text.replace(/\\\((.*?)\\\)/g, (match, latex) => {
            return '$' + latex.trim() + '$';
        });

        // 4. Handle plain square brackets with LaTeX commands (common in some models)
        // Display math: [ \command{...} ] with newlines
        text = text.replace(/\[\s*\n\s*(\\[a-zA-Z]+[\s\S]*?)\s*\n\s*\]/g, (match, latex) => {
            return '\n$$' + latex.trim() + '$$\n';
        });

        // 5. Inline square brackets with LaTeX: [ \command{...} ]
        text = text.replace(/\[\s*(\\[a-zA-Z]+[^\]]*?)\s*\]/g, (match, latex) => {
            return '$$' + latex.trim() + '$$';
        });

        // 6. Handle display math on separate lines (common pattern)
        // Detects lines that start with LaTeX commands
        text = text.replace(/^\s*(\\[a-zA-Z]+\{[\s\S]*?\})\s*$/gm, (match, latex) => {
            return '$$' + latex.trim() + '$$';
        });

        // 7. Ensure proper spacing around display math
        text = text.replace(/\$\$([\s\S]*?)\$\$/g, (match, latex) => {
            return '\n$$' + latex.trim() + '$$\n';
        });

        // 8. Restore code blocks
        text = text.replace(/__CODE_BLOCK_(\d+)__/g, (match, index) => {
            return codeBlocks[parseInt(index)];
        });

        // Configure marked.js for better code block handling
        marked.setOptions({
            breaks: true,
            gfm: true,
            langPrefix: 'language-' // Prism expects this prefix
        });

        // Use marked.js for markdown conversion
        let html = marked.parse(text);

        return html;
    }

    function renderMath(element) {
        // === ROBUST KATEX MATH RENDERING ===
        // This function guarantees 100% math rendering using KaTeX

        if (!element) return;

        // Check if KaTeX and auto-render are loaded
        if (window.renderMathInElement) {
            try {
                // KaTeX auto-render with comprehensive delimiter support
                renderMathInElement(element, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '$', right: '$', display: false},
                        {left: '\\[', right: '\\]', display: true},
                        {left: '\\(', right: '\\)', display: false}
                    ],
                    throwOnError: false,
                    errorColor: '#cc0000',
                    strict: false,
                    trust: false,
                    macros: {
                        "\\RR": "\\mathbb{R}",
                        "\\NN": "\\mathbb{N}",
                        "\\ZZ": "\\mathbb{Z}",
                        "\\QQ": "\\mathbb{Q}",
                        "\\CC": "\\mathbb{C}"
                    },
                    fleqn: false,
                    leqno: false,
                    minRuleThickness: 0.04
                });
            } catch (err) {
                console.warn('KaTeX rendering error:', err);
                // Fallback: try manual rendering for any missed equations
                fallbackMathRender(element);
            }
        } else {
            // KaTeX not loaded yet, wait and retry with exponential backoff
            const maxRetries = 10;
            const initialDelay = 50;

            const retryRender = (attempt = 0) => {
                if (window.renderMathInElement) {
                    renderMath(element); // Retry with full function
                } else if (attempt < maxRetries) {
                    const delay = initialDelay * Math.pow(1.5, attempt);
                    setTimeout(() => retryRender(attempt + 1), delay);
                } else {
                    console.warn('KaTeX failed to load after', maxRetries, 'attempts');
                    fallbackMathRender(element);
                }
            };

            retryRender(0);
        }
    }

    function fallbackMathRender(element) {
        // Manual fallback rendering for edge cases
        if (!window.katex) return;

        // Find and render display math ($$...$$)
        const displayMathRegex = /\$\$([\s\S]+?)\$\$/g;
        element.innerHTML = element.innerHTML.replace(displayMathRegex, (match, tex) => {
            try {
                return '<span class="katex-display">' + katex.renderToString(tex.trim(), {
                    displayMode: true,
                    throwOnError: false
                }) + '</span>';
            } catch (e) {
                return match; // Keep original if rendering fails
            }
        });

        // Find and render inline math ($...$)
        const inlineMathRegex = /\$([^\$]+?)\$/g;
        element.innerHTML = element.innerHTML.replace(inlineMathRegex, (match, tex) => {
            try {
                return katex.renderToString(tex.trim(), {
                    displayMode: false,
                    throwOnError: false
                });
            } catch (e) {
                return match; // Keep original if rendering fails
            }
        });
    }

    function addCopyButtons(container) {
        const codeBlocks = container.querySelectorAll('pre');
        codeBlocks.forEach(block => {
            // Check if copy button already exists
            if (block.querySelector('.copy-btn')) {
                return;
            }

            const codeElement = block.querySelector('code');

            // Add copy button
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
            copyBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                const code = codeElement.textContent;

                // Try modern clipboard API first
                if (navigator.clipboard && window.isSecureContext) {
                    try {
                        await navigator.clipboard.writeText(code);
                        copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                        setTimeout(() => {
                            copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                        }, 2000);
                        return;
                    } catch (err) {
                        console.warn('Clipboard API failed, using fallback:', err);
                    }
                }

                // Fallback method for iOS and older browsers
                const textArea = document.createElement('textarea');
                textArea.value = code;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();

                try {
                    const successful = document.execCommand('copy');
                    if (successful) {
                        copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                        setTimeout(() => {
                            copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                        }, 2000);
                    } else {
                        copyBtn.innerHTML = '<i class="fa-solid fa-times"></i> Failed';
                        setTimeout(() => {
                            copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                        }, 2000);
                    }
                } catch (err) {
                    console.error('Failed to copy text: ', err);
                    copyBtn.innerHTML = '<i class="fa-solid fa-times"></i> Failed';
                    setTimeout(() => {
                        copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                    }, 2000);
                } finally {
                    document.body.removeChild(textArea);
                }
            });
            block.appendChild(copyBtn);

            // Add language label if language is detected
            if (codeElement && codeElement.className) {
                const languageMatch = codeElement.className.match(/language-(\w+)/);
                if (languageMatch && languageMatch[1] && languageMatch[1] !== 'none') {
                    const language = languageMatch[1];
                    const languageLabel = document.createElement('div');
                    languageLabel.className = 'code-language-label';

                    // Map common language aliases to display names
                    const languageNames = {
                        'js': 'JavaScript',
                        'javascript': 'JavaScript',
                        'ts': 'TypeScript',
                        'typescript': 'TypeScript',
                        'py': 'Python',
                        'python': 'Python',
                        'java': 'Java',
                        'cpp': 'C++',
                        'c': 'C',
                        'csharp': 'C#',
                        'cs': 'C#',
                        'go': 'Go',
                        'rust': 'Rust',
                        'ruby': 'Ruby',
                        'php': 'PHP',
                        'sql': 'SQL',
                        'bash': 'Bash',
                        'sh': 'Shell',
                        'json': 'JSON',
                        'yaml': 'YAML',
                        'yml': 'YAML',
                        'html': 'HTML',
                        'css': 'CSS',
                        'scss': 'SCSS',
                        'jsx': 'React JSX',
                        'tsx': 'React TSX',
                        'markdown': 'Markdown',
                        'md': 'Markdown',
                        'docker': 'Docker',
                        'dockerfile': 'Dockerfile'
                    };

                    languageLabel.textContent = languageNames[language.toLowerCase()] || language.toUpperCase();
                    block.appendChild(languageLabel);
                }
            }
        });
    }

    newChatBtn.addEventListener('click', function() {
        currentSessionId = null;
        localStorage.removeItem('session_id');
        chatMessages.innerHTML = '';
        clearAttachments(); // Clear any pending attachments
        resetTotalTokensDisplay(); // Reset token counter for new chat

        // Scroll to top to show logo and welcome message
        chatMessages.scrollTop = 0;
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Additional scroll for mobile devices
        setTimeout(() => {
            chatMessages.scrollTop = 0;
            window.scrollTo({ top: 0, behavior: 'instant' });
        }, 50);

        if (isBotTyping) {
            setBotTyping(false);
        }
        loadSessions();
    });

    function loadSessions() {
        fetch('/api/sessions')
            .then(async response => {
                // Check for session expiration
                if (await handleSessionExpiration(response)) {
                    return null;
                }
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(sessions => {
                if (!sessions) return; // Session expired, already handled
                sessionList.innerHTML = '';
                const template = document.getElementById('session-item-template');
                sessions.forEach(session => {
                    const sessionItem = template.content.cloneNode(true);
                    const sessionItemDiv = sessionItem.querySelector('.session-item');
                    const sessionNameDiv = sessionItem.querySelector('.session-name');
                    const sessionNameInput = sessionItem.querySelector('.session-name-input');
                    const menuBtn = sessionItem.querySelector('.session-menu-btn');
                    const menuDropdown = sessionItem.querySelector('.session-menu-dropdown');
                    const editBtn = sessionItem.querySelector('.edit-chat-btn');
                    const exportBtn = sessionItem.querySelector('.export-chat-btn');
                    const deleteBtn = sessionItem.querySelector('.delete-chat-btn');

                    sessionNameDiv.textContent = session.name;
                    sessionItemDiv.dataset.sessionId = session.session_id;

                    // Add active class if this is the current session
                    if (session.session_id === currentSessionId) {
                        sessionItemDiv.classList.add('active');
                    }

                    sessionItemDiv.addEventListener('click', (e) => {
                        // Don't trigger if clicking on menu button, dropdown, or input
                        if (e.target.closest('.session-menu-btn') ||
                            e.target.closest('.session-menu-dropdown') ||
                            e.target.closest('.session-name-input')) {
                            return;
                        }

                        // Remove active class from all sessions
                        document.querySelectorAll('.session-item').forEach(item => {
                            item.classList.remove('active');
                        });

                        // Add active class to clicked session
                        sessionItemDiv.classList.add('active');

                        currentSessionId = session.session_id;
                        localStorage.setItem('session_id', currentSessionId);
                        loadChatHistory(currentSessionId);

                        // Close sidebar after selecting session
                        closeAllSidebars();
                    });

                    // Menu button toggle
                    menuBtn.addEventListener('click', (e) => {
                        e.stopPropagation();

                        // Close all other open menus
                        document.querySelectorAll('.session-menu-dropdown.show').forEach(dropdown => {
                            if (dropdown !== menuDropdown) {
                                dropdown.classList.remove('show');
                                dropdown.previousElementSibling.classList.remove('active');
                            }
                        });

                        // Toggle current menu
                        menuDropdown.classList.toggle('show');
                        menuBtn.classList.toggle('active');
                    });

                    // Edit button functionality
                    editBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        menuDropdown.classList.remove('show');
                        menuBtn.classList.remove('active');
                        sessionNameDiv.style.display = 'none';
                        sessionNameInput.style.display = 'block';
                        sessionNameInput.value = session.name;
                        sessionNameInput.focus();
                        sessionNameInput.select();
                    });

                    // Export button functionality
                    exportBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        menuDropdown.classList.remove('show');
                        menuBtn.classList.remove('active');
                        exportChat(session.session_id);
                    });

                    // Save on blur or Enter key
                    const saveRename = async () => {
                        const newName = sessionNameInput.value.trim();
                        if (newName && newName !== session.name) {
                            try {
                                const response = await fetch(`/api/rename_chat/${session.session_id}`, {
                                    method: 'PUT',
                                    headers: {
                                        'Content-Type': 'application/json'
                                    },
                                    body: JSON.stringify({ name: newName })
                                });

                                // Check for session expiration
                                if (await handleSessionExpiration(response)) {
                                    return;
                                }

                                if (response.ok) {
                                    session.name = newName;
                                    sessionNameDiv.textContent = newName;
                                }
                            } catch (error) {
                                console.error('Failed to rename chat:', error);
                            }
                        }
                        sessionNameDiv.style.display = 'block';
                        sessionNameInput.style.display = 'none';
                    };

                    sessionNameInput.addEventListener('blur', saveRename);
                    sessionNameInput.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            saveRename();
                        } else if (e.key === 'Escape') {
                            sessionNameDiv.style.display = 'block';
                            sessionNameInput.style.display = 'none';
                        }
                    });

                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        menuDropdown.classList.remove('show');
                        menuBtn.classList.remove('active');
                        deleteSession(session.session_id);
                    });

                    sessionList.appendChild(sessionItem);
                });
            });
    }

    // Close all menus when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.session-actions')) {
            document.querySelectorAll('.session-menu-dropdown.show').forEach(dropdown => {
                dropdown.classList.remove('show');
            });
            document.querySelectorAll('.session-menu-btn.active').forEach(btn => {
                btn.classList.remove('active');
            });
        }
    });

    // Export chat function
    function exportChat(sessionId) {
        // Create a temporary link and trigger download
        const link = document.createElement('a');
        link.href = `/api/export_chat/${sessionId}`;
        link.download = '';  // Filename is set by the server
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    const deleteConfirmationModal = document.getElementById('delete-confirmation-modal');
    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    const cancelDeleteBtn = document.getElementById('cancel-delete-btn');
    let sessionToDelete = null;

    function deleteSession(sessionId) {
        sessionToDelete = sessionId;
        deleteConfirmationModal.style.display = 'flex';
    }

    function confirmDeleteSession() {
        if (!sessionToDelete) return;

        fetch(`/api/delete_chat/${sessionToDelete}`, {
            method: 'DELETE'
        })
        .then(async response => {
            // Check for session expiration
            if (await handleSessionExpiration(response)) {
                return null;
            }
            return response.json();
        })
        .then(data => {
            if (!data) return; // Session expired, already handled
            if (data.status === 'success') {
                if (currentSessionId === sessionToDelete) {
                    currentSessionId = null;
                    localStorage.removeItem('session_id');
                    chatMessages.innerHTML = '';
                }
                loadSessions();
            } else {
                alert('Error deleting chat: ' + (data.message || 'Unknown error.'));
            }
        })
        .catch(error => {
            console.error('Error deleting chat:', error);
            alert('An error occurred while deleting the chat.');
        })
        .finally(() => {
            sessionToDelete = null;
            deleteConfirmationModal.style.display = 'none';
        });
    }

    confirmDeleteBtn.addEventListener('click', confirmDeleteSession);

    cancelDeleteBtn.addEventListener('click', () => {
        sessionToDelete = null;
        deleteConfirmationModal.style.display = 'none';
    });

    function loadChatHistory(sessionId) {
        fetch(`/api/history?session_id=${sessionId}`)
            .then(async response => {
                // Check for session expiration first
                if (await handleSessionExpiration(response)) {
                    return null;
                }
                if (!response.ok) {
                    // Handle non-OK responses
                    if (response.status === 404) {
                        // Session not found (deleted on another device)
                        console.warn(`Session ${sessionId} not found, clearing and refreshing...`);

                        // Clear the invalid session from localStorage
                        if (currentSessionId === sessionId) {
                            currentSessionId = null;
                            localStorage.removeItem('session_id');
                        }

                        // Refresh the session list to remove deleted sessions
                        loadSessions();

                        // Clear the chat messages and show welcome message
                        chatMessages.innerHTML = '';
                        ensureWelcomeMessage();
                        toggleWelcomeMessage();

                        return null; // Don't continue processing
                    }
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(history => {
                if (!history) return; // Session was not found, already handled above

                chatMessages.innerHTML = '';

                // Scroll to top to show logo and welcome message
                chatMessages.scrollTop = 0;
                window.scrollTo({ top: 0, behavior: 'smooth' });

                // Additional scroll for mobile devices
                setTimeout(() => {
                    chatMessages.scrollTop = 0;
                    window.scrollTo({ top: 0, behavior: 'instant' });
                }, 0);

                // Re-insert welcome message (it will be hidden if there are messages)
                ensureWelcomeMessage();

                // Detect the model used in this chat and restore selection
                let sessionModelUsed = null;
                for (const item of history) {
                    // Look for bot/assistant messages with model_used field
                    if ((item.role === 'assistant' || item.role === 'bot') && item.model_used) {
                        sessionModelUsed = item.model_used;
                        break; // Use the first bot message's model
                    }
                }

                // Restore model selection if detected
                if (sessionModelUsed) {
                    const modelSelection = mapModelUsedToSelection(sessionModelUsed);
                    if (modelSelection) {
                        updateModelSelectionUI(modelSelection.model, modelSelection.provider);
                    }
                }

                history.forEach(item => {
                    // Convert 'assistant' role to 'bot' for proper rendering
                    const role = item.role === 'assistant' ? 'bot' : item.role;

                    // Extract thinking content if present (for bot messages)
                    let thinkingContent = null;
                    let content = item.content;
                    if (role === 'bot') {
                        const thinkingMatch = content.match(/<think>(.*?)<\/think>/s);
                        if (thinkingMatch) {
                            thinkingContent = thinkingMatch[1].trim();
                            content = content.replace(/<think>.*?<\/think>/gs, '').trim();
                        }
                    }

                    // Get token count based on role
                    const tokenCount = role === 'user' ? item.input_tokens : item.output_tokens;
                    const tokensEstimated = item.tokens_estimated || false;
                    addMessage(content, role, item.attachments, item.created_at, item.model_used, thinkingContent, item.id, tokenCount, tokensEstimated);
                });

                // Update total tokens display after loading history
                updateTotalTokensDisplay();

                // Re-apply syntax highlighting and copy buttons to all code blocks
                // This ensures formatting is preserved when switching between chats
                setTimeout(() => {
                    chatMessages.querySelectorAll('.message.bot .actual-content-wrapper').forEach(wrapper => {
                        wrapper.querySelectorAll('pre code').forEach((block) => {
                            if (window.Prism) {
                                Prism.highlightElement(block);
                            }
                        });
                        addCopyButtons(wrapper);
                    });
                }, 100);

                // Toggle welcome message visibility based on message count
                toggleWelcomeMessage();
            })
            .catch(error => {
                console.error('Error loading chat history:', error);
                // On error, clear the chat and show welcome message
                chatMessages.innerHTML = '';
                ensureWelcomeMessage();
                toggleWelcomeMessage();
            });
    }

    // Initial check for welcome message visibility
    toggleWelcomeMessage();
});