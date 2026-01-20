// Settings Page JavaScript

let currentUser = null;
let isAdmin = false;

// Default child safety prompts (from add_child_safety_settings.py migration)
const DEFAULT_CHILD_PROMPT = `You are a helpful, friendly AI assistant talking with a child under 12 years old.
Please follow these guidelines:
- Use simple, age-appropriate language
- Never discuss violence, adult themes, or scary content
- Encourage learning and creativity
- Be patient and supportive
- If asked about inappropriate topics, gently redirect to child-friendly subjects
- Never collect personal information or encourage sharing private details
- Promote safety and responsible behaviour`;

const DEFAULT_TEEN_PROMPT = `You are a helpful AI assistant talking with a teenager (12-17 years old).
Please follow these guidelines:
- Be informative while maintaining age-appropriate boundaries
- Avoid explicit content, violence, or harmful advice
- Encourage critical thinking and learning
- If asked about sensitive topics, provide balanced, educational responses
- Never encourage dangerous activities or substance use
- Support mental health and recommend professional help when appropriate
- Protect user privacy and personal information`;

// =============================================================================
// Model ID Selector Functions
// =============================================================================

// Model list cache (provider -> {models: [], timestamp: number})
const modelListCache = {};
const MODEL_CACHE_TTL = 300000; // 5 minutes in milliseconds

/**
 * Fetch available models from a provider's API
 * @param {string} provider - Provider name (gemini, openai, anthropic, xai, lm_studio, ollama)
 * @param {boolean} forceRefresh - Bypass cache
 * @returns {Promise<{success: boolean, models?: Array, error?: string}>}
 */
async function fetchAvailableModels(provider, forceRefresh = false) {
    // Check cache first (unless force refresh)
    if (!forceRefresh && modelListCache[provider]) {
        const cached = modelListCache[provider];
        if (Date.now() - cached.timestamp < MODEL_CACHE_TTL) {
            return { success: true, models: cached.models, cached: true };
        }
    }

    try {
        const url = `/api/admin/available-models/${provider}${forceRefresh ? '?refresh=true' : ''}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.status === 'success') {
            // Cache the results
            modelListCache[provider] = {
                models: data.models,
                timestamp: Date.now()
            };
            return { success: true, models: data.models, cached: data.cached || false };
        } else {
            return {
                success: false,
                error: data.message || 'Failed to fetch models',
                allowManualEntry: data.allow_manual_entry !== false
            };
        }
    } catch (error) {
        return {
            success: false,
            error: 'Network error while fetching models',
            allowManualEntry: true
        };
    }
}

/**
 * Get the HTML ID prefix for a provider (handles lm_studio -> lm-studio conversion)
 * @param {string} provider - Provider name
 * @returns {string} HTML-safe ID prefix
 */
function getProviderHtmlId(provider) {
    return provider.replace('_', '-');
}

/**
 * Get the API provider name from HTML ID (handles lm-studio -> lm_studio conversion)
 * @param {string} htmlId - HTML ID prefix
 * @returns {string} API provider name
 */
function getProviderApiName(htmlId) {
    return htmlId.replace('-', '_');
}

/**
 * Populate a model selector dropdown with fetched models
 * @param {string} provider - Provider name (API format: lm_studio)
 * @param {Array} models - Array of {id, name} objects
 * @param {string} currentValue - Currently selected model ID
 */
function populateModelDropdown(provider, models, currentValue = '') {
    const htmlId = getProviderHtmlId(provider);
    const select = document.getElementById(`${htmlId}-model-id-select`);
    const input = document.getElementById(`${htmlId}-model-id`);

    if (!select) return;

    // Clear existing options (keep first two: placeholder and custom)
    while (select.options.length > 2) {
        select.remove(2);
    }

    // Add model options
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.id;
        option.textContent = model.name !== model.id ? `${model.name} (${model.id})` : model.id;
        select.appendChild(option);
    });

    // Set current value
    if (currentValue) {
        const hasOption = Array.from(select.options).some(opt => opt.value === currentValue);
        if (hasOption) {
            select.value = currentValue;
            input.style.display = 'none';
            select.style.display = '';
        } else {
            // Current value not in list - show as custom
            select.value = '__custom__';
            input.value = currentValue;
            input.style.display = '';
            select.style.display = 'none';
        }
    } else {
        // No current value - show dropdown
        select.value = '';
        input.style.display = 'none';
        select.style.display = '';
    }
}

/**
 * Handle refresh button click for a provider
 * @param {string} provider - Provider name (API format: lm_studio)
 */
async function handleRefreshModels(provider) {
    const htmlId = getProviderHtmlId(provider);
    const btn = document.querySelector(`.btn-refresh-models[data-provider="${provider}"]`);
    const status = document.getElementById(`${htmlId}-model-status`);
    const select = document.getElementById(`${htmlId}-model-id-select`);
    const input = document.getElementById(`${htmlId}-model-id`);

    if (!btn || !status) return;

    // Show loading state
    btn.classList.add('loading');
    btn.disabled = true;
    select.disabled = true;
    status.className = 'model-selector-status loading';
    status.textContent = 'Fetching models...';

    const result = await fetchAvailableModels(provider, true);

    // Remove loading state
    btn.classList.remove('loading');
    btn.disabled = false;
    select.disabled = false;

    if (result.success) {
        // Get current value from either select or input
        let currentValue = select.style.display === 'none' ? input.value :
                            (select.value && select.value !== '__custom__' ? select.value : input.value);

        // If the current value is not in the new list of models, clear it so the dropdown is shown
        // This prevents the UI from getting stuck in "custom input" mode when the user refreshes
        // and the current model ID (e.g. default) is not in the returned list
        const modelExists = result.models.some(m => m.id === currentValue);
        if (currentValue && !modelExists) {
            currentValue = '';
        }

        populateModelDropdown(provider, result.models, currentValue);

        status.className = 'model-selector-status success';
        status.textContent = `Found ${result.models.length} model(s)`;

        // Clear status after 3 seconds
        setTimeout(() => {
            status.textContent = '';
            status.className = 'model-selector-status';
        }, 3000);
    } else {
        status.className = 'model-selector-status error';
        status.textContent = result.error;

        // Switch to manual entry mode if allowed
        if (result.allowManualEntry) {
            select.style.display = 'none';
            input.style.display = '';
        }
    }
}

/**
 * Handle model selector dropdown change
 * @param {Event} event - Change event
 */
function handleModelSelectChange(event) {
    const select = event.target;
    const provider = select.dataset.provider;
    const htmlId = getProviderHtmlId(provider);
    const input = document.getElementById(`${htmlId}-model-id`);

    if (select.value === '__custom__') {
        // Show text input for custom entry
        select.style.display = 'none';
        input.style.display = '';
        input.focus();
    } else if (select.value === '') {
        // Placeholder selected - no action
        input.value = '';
    } else {
        // Model selected - update hidden input
        input.value = select.value;
    }
}

/**
 * Handle model ID input blur (switch back to dropdown if empty)
 * @param {Event} event - Blur event
 */
function handleModelInputBlur(event) {
    const input = event.target;
    // Extract provider from input ID (e.g., "gemini-model-id" -> "gemini")
    const htmlId = input.id.replace('-model-id', '');
    const select = document.getElementById(`${htmlId}-model-id-select`);

    if (!input.value.trim() && select && select.options.length > 2) {
        // If input is empty and we have model options, switch back to dropdown
        input.style.display = 'none';
        select.style.display = '';
        select.value = '';
    }
}

/**
 * Initialize a model selector with current value
 * @param {string} provider - Provider name (API format: lm_studio)
 * @param {string} currentValue - Current model ID value
 */
async function initializeModelSelector(provider, currentValue) {
    const htmlId = getProviderHtmlId(provider);
    const select = document.getElementById(`${htmlId}-model-id-select`);
    const input = document.getElementById(`${htmlId}-model-id`);

    if (!select || !input) return;

    // Set input value immediately
    input.value = currentValue || '';

    // Try to fetch models (use cache)
    const result = await fetchAvailableModels(provider, false);

    if (result.success && result.models.length > 0) {
        populateModelDropdown(provider, result.models, currentValue);
    } else {
        // No models fetched - show text input mode
        select.style.display = 'none';
        input.style.display = '';
    }
}

/**
 * Get the model ID value from either select or input
 * @param {string} provider - Provider name (API format: lm_studio)
 * @returns {string} The model ID value
 */
function getModelIdValue(provider) {
    const htmlId = getProviderHtmlId(provider);
    const select = document.getElementById(`${htmlId}-model-id-select`);
    const input = document.getElementById(`${htmlId}-model-id`);

    // If dropdown is visible and has a valid selection (not placeholder or custom)
    if (select && select.style.display !== 'none' && select.value && select.value !== '__custom__' && select.value !== '') {
        return select.value;
    }
    // Otherwise use the input value
    return input ? input.value.trim() : '';
}

// Initialize theme on page load
function initTheme() {
    // Get saved theme from localStorage (same as main app)
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.getElementById('theme-select').value = savedTheme;

    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
}

// Load settings on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize theme first for consistent appearance
    initTheme();

    // Load user info to check admin status
    await loadUserInfo();

    // Load general settings
    loadGeneralSettings();

    // Load admin settings if user is admin
    if (isAdmin) {
        await loadAdminModels();
        await loadAdminSettings();
        await loadRateLimitSettings();
        await loadChildSafetySettings();
        await loadAPIKeys();
        await loadLocalModelSettings();
        setupModelSettingsListeners();
        setupRateLimitListeners();
        setupChildSafetyListeners();
    }

    // Setup event listeners
    setupEventListeners();
});

// Load user information
async function loadUserInfo() {
    try {
        const response = await fetch('/auth/me');
        if (!response.ok) {
            if (response.status === 401) {
                window.location.href = '/auth/login';
                return;
            }
            throw new Error('Failed to load user info');
        }

        const data = await response.json();
        currentUser = data.user;
        isAdmin = data.is_super_admin || false;

        // Show admin section if user is super admin
        if (isAdmin) {
            document.getElementById('admin-settings-section').style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading user info:', error);
    }
}

// Load general settings from localStorage
function loadGeneralSettings() {
    // Load theme (already done in initTheme)

    // Load start fresh setting (default to true if not set)
    const startFreshValue = localStorage.getItem('startFreshSession');
    const startFresh = startFreshValue === null ? true : startFreshValue === 'true';
    document.getElementById('start-fresh-toggle').checked = startFresh;
}

// Load admin models
async function loadAdminModels() {
    if (!isAdmin) return;

    const modelsList = document.getElementById('admin-models-list');

    try {
        const response = await fetch('/api/admin/models');
        if (!response.ok) {
            throw new Error('Failed to load models');
        }

        const data = await response.json();
        const models = data.models || [];

        // Clear loading message
        modelsList.innerHTML = '';

        // Create model items
        models.forEach(model => {
            const modelItem = createModelItem(model);
            modelsList.appendChild(modelItem);
        });

        if (models.length === 0) {
            modelsList.innerHTML = '<p style="text-align: center; color: var(--profile-text-tertiary); padding: 20px;">No models available</p>';
        }
    } catch (error) {
        console.error('Error loading models:', error);
        modelsList.innerHTML = `<p style="text-align: center; color: #c53030; padding: 20px;"><i class="fas fa-exclamation-circle"></i> Failed to load models</p>`;
    }
}

// Create model item HTML
function createModelItem(model) {
    const div = document.createElement('div');
    div.className = 'admin-model-item';
    div.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 16px; background: var(--profile-input-bg); border: 1px solid var(--profile-border-light); border-radius: 8px; margin-bottom: 12px; transition: all 0.2s ease;';

    const infoDiv = document.createElement('div');
    infoDiv.style.cssText = 'flex: 1; display: flex; align-items: center; gap: 12px;';

    // Model icon
    const icon = document.createElement('img');
    icon.src = model.icon_path || '/static/images/default.png';
    icon.alt = model.display_name;
    icon.style.cssText = 'width: 24px; height: 24px; object-fit: contain;';

    // Model name
    const nameSpan = document.createElement('span');
    nameSpan.textContent = model.display_name;
    nameSpan.style.cssText = 'font-weight: 600; color: var(--profile-text-primary);';

    infoDiv.appendChild(icon);
    infoDiv.appendChild(nameSpan);

    const toggleLabel = document.createElement('label');
    toggleLabel.className = 'toggle-switch';
    toggleLabel.style.margin = '0';

    const toggleInput = document.createElement('input');
    toggleInput.type = 'checkbox';
    toggleInput.checked = model.is_enabled;
    toggleInput.dataset.modelId = model.id;
    toggleInput.addEventListener('change', () => handleModelToggle(model.id, toggleInput.checked));

    const toggleSlider = document.createElement('span');
    toggleSlider.className = 'toggle-slider';

    toggleLabel.appendChild(toggleInput);
    toggleLabel.appendChild(toggleSlider);

    div.appendChild(infoDiv);
    div.appendChild(toggleLabel);

    return div;
}

// Handle model visibility toggle
async function handleModelToggle(modelId, isEnabled) {
    try {
        const response = await fetch(`/api/admin/models/${modelId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ is_enabled: isEnabled })
        });

        if (!response.ok) {
            throw new Error('Failed to update model visibility');
        }

        showSuccess('admin-settings-success', 'Model visibility updated successfully!');
    } catch (error) {
        console.error('Error updating model visibility:', error);
        showError('admin-settings-error', 'Failed to update model visibility. Please try again.');
        // Reload models to restore previous state
        await loadAdminModels();
    }
}

// Load admin settings
async function loadAdminSettings() {
    if (!isAdmin) return;

    // Load sensitive info filter setting
    await loadBooleanSetting('sensitive_info_filter_enabled', 'sensitive-info-filter-toggle');

    // Load distilled context setting
    await loadBooleanSetting('distilled_context_enabled', 'distilled-context-toggle');
}

// Helper function to load a boolean setting
async function loadBooleanSetting(settingKey, elementId) {
    try {
        const response = await fetch(`/api/admin/settings/${settingKey}`);

        // If setting doesn't exist (404), default to false
        if (response.status === 404) {
            console.log(`Setting ${settingKey} not found, defaulting to false`);
            const element = document.getElementById(elementId);
            if (element) element.checked = false;
            return;
        }

        if (!response.ok) {
            throw new Error(`Failed to load setting: ${settingKey}`);
        }

        const data = await response.json();

        // Handle boolean true, string 'True', 'true', '1', 'yes', 'on'
        const settingValue = data.setting?.setting_value;
        let enabled = false;

        if (typeof settingValue === 'boolean') {
            enabled = settingValue;
        } else if (typeof settingValue === 'string') {
            enabled = settingValue.toLowerCase() === 'true' ||
                      settingValue === '1' ||
                      settingValue.toLowerCase() === 'yes' ||
                      settingValue.toLowerCase() === 'on';
        }

        const element = document.getElementById(elementId);
        if (element) element.checked = enabled;
    } catch (error) {
        console.error(`Error loading setting ${settingKey}:`, error);
        const element = document.getElementById(elementId);
        if (element) element.checked = false;
    }
}

// Setup event listeners
function setupEventListeners() {
    // Theme selector
    document.getElementById('theme-select').addEventListener('change', (e) => {
        const theme = e.target.value;
        localStorage.setItem('theme', theme);

        if (theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }

        showSuccess('general-settings-success', 'Theme updated successfully!');
    });

    // Start fresh toggle
    document.getElementById('start-fresh-toggle').addEventListener('change', (e) => {
        const startFresh = e.target.checked;
        localStorage.setItem('startFreshSession', startFresh.toString());
        showSuccess('general-settings-success', 'Chat behavior updated successfully!');
    });

    // Sensitive info filter toggle (admin only)
    if (isAdmin) {
        document.getElementById('sensitive-info-filter-toggle').addEventListener('change', async (e) => {
            const enabled = e.target.checked;
            await updateAdminSetting('sensitive_info_filter_enabled', enabled);
        });

        // Distilled context toggle (admin only)
        document.getElementById('distilled-context-toggle').addEventListener('change', async (e) => {
            const enabled = e.target.checked;
            await updateAdminSetting('distilled_context_enabled', enabled);
        });
    }

    // Back to chat buttons
    document.getElementById('back-to-chat-btn-top').addEventListener('click', () => {
        window.location.href = '/';
    });

    document.getElementById('back-to-chat-btn').addEventListener('click', () => {
        window.location.href = '/';
    });

    // Profile link button
    document.getElementById('profile-link-btn').addEventListener('click', () => {
        window.location.href = '/auth/profile';
    });
}

// Update admin setting
async function updateAdminSetting(key, value) {
    if (!isAdmin) return;

    try {
        const response = await fetch(`/api/admin/settings/${key}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                value: value,
                setting_type: 'boolean'
            })
        });

        if (!response.ok) {
            throw new Error('Failed to update admin setting');
        }

        showSuccess('admin-settings-success', 'Admin setting updated successfully!');
    } catch (error) {
        console.error('Error updating admin setting:', error);
        showError('admin-settings-error', 'Failed to update admin setting. Please try again.');
        // Reload settings to restore previous state
        await loadAdminSettings();
    }
}

// Show success message
function showSuccess(elementId, message) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.style.display = 'block';

    setTimeout(() => {
        element.style.display = 'none';
    }, 3000);
}

// Show error message
function showError(elementId, message) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.style.display = 'block';

    setTimeout(() => {
        element.style.display = 'none';
    }, 5000);
}

// ==========================================
// API Model Settings (Admin Only)
// ==========================================

// Load API Keys
async function loadAPIKeys() {
    if (!isAdmin) return;

    try {
        const response = await fetch('/api/config');
        if (!response.ok) {
            console.error('Failed to load API keys');
            return;
        }

        const data = await response.json();

        // Provider mapping for remove buttons
        const providers = ['gemini', 'openai', 'anthropic', 'xai'];

        providers.forEach(provider => {
            const input = document.getElementById(`${provider}-api-key`);
            const removeBtn = document.querySelector(`.remove-api-key-btn[data-provider="${provider}"]`);
            const keyValue = data[`${provider}_api_key`];

            if (input) {
                if (keyValue) {
                    input.placeholder = `Current: ${keyValue}`;
                    if (removeBtn) removeBtn.style.display = 'inline-flex';
                } else {
                    input.placeholder = `Enter system ${provider.charAt(0).toUpperCase() + provider.slice(1)} API key`;
                    if (removeBtn) removeBtn.style.display = 'none';
                }
            }
        });

    } catch (error) {
        console.error('Error loading API keys:', error);
    }
}

// Remove API Key handler
async function removeApiKey(provider) {
    if (!confirm(`Are you sure you want to remove the system ${provider.toUpperCase()} API key? This will affect all users.`)) {
        return;
    }

    const errorDiv = document.getElementById('api-keys-error');
    const successDiv = document.getElementById('api-keys-success');

    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';

    try {
        // Send empty string to trigger deletion
        const payload = {};
        payload[`${provider}_api_key`] = '';

        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            successDiv.textContent = `System ${provider.toUpperCase()} API key removed successfully`;
            successDiv.style.display = 'block';
            await loadAPIKeys();
        } else {
            errorDiv.textContent = data.error || 'Failed to remove API key';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error. Please try again.';
        errorDiv.style.display = 'block';
    }
}

// Load Local Model Settings (now uses /api/config for system-level settings)
async function loadLocalModelSettings() {
    if (!isAdmin) return;

    try {
        const response = await fetch('/api/config');
        if (!response.ok) {
            console.error('Failed to load settings');
            return;
        }

        const settings = await response.json();

        // Populate local model form fields (URLs only - model IDs handled by selectors)
        const lmStudioUrl = document.getElementById('lm-studio-url');
        const ollamaUrl = document.getElementById('ollama-url');

        if (lmStudioUrl) lmStudioUrl.value = settings.lm_studio_url || '';
        if (ollamaUrl) ollamaUrl.value = settings.ollama_url || '';

        // Initialize model selectors with current values
        // These will attempt to fetch model lists and populate dropdowns
        const modelSettings = {
            'gemini': settings.gemini_model_id || '',
            'openai': settings.openai_model_id || '',
            'anthropic': settings.anthropic_model_id || '',
            'xai': settings.xai_model_id || '',
            'lm_studio': settings.lm_studio_model_id || '',
            'ollama': settings.ollama_model_id || ''
        };

        // Initialize model selectors in parallel (but don't block)
        Object.entries(modelSettings).forEach(([provider, currentValue]) => {
            initializeModelSelector(provider, currentValue);
        });

    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// Setup model settings event listeners (Admin Only)
function setupModelSettingsListeners() {
    if (!isAdmin) return;

    // Initialize remove button handlers
    document.querySelectorAll('.remove-api-key-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const provider = btn.dataset.provider;
            removeApiKey(provider);
        });
    });

    // Setup model selector event listeners
    const providers = ['gemini', 'openai', 'anthropic', 'xai', 'lm_studio', 'ollama'];

    providers.forEach(provider => {
        const htmlId = getProviderHtmlId(provider);
        const select = document.getElementById(`${htmlId}-model-id-select`);
        const input = document.getElementById(`${htmlId}-model-id`);
        const refreshBtn = document.querySelector(`.btn-refresh-models[data-provider="${provider}"]`);

        if (select) {
            select.addEventListener('change', handleModelSelectChange);
        }

        if (input) {
            input.addEventListener('blur', handleModelInputBlur);
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                handleRefreshModels(provider);
            });
        }
    });

    // API Keys and Model IDs form submission (all saved to /api/config)
    const apiKeysForm = document.getElementById('api-keys-form');
    if (apiKeysForm) {
        apiKeysForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const geminiKey = document.getElementById('gemini-api-key').value.trim();
            const openaiKey = document.getElementById('openai-api-key').value.trim();
            const anthropicKey = document.getElementById('anthropic-api-key').value.trim();
            const xaiKey = document.getElementById('xai-api-key').value.trim();

            // Get model IDs from selectors (handles both dropdown and text input)
            const geminiModelId = getModelIdValue('gemini');
            const openaiModelId = getModelIdValue('openai');
            const anthropicModelId = getModelIdValue('anthropic');
            const xaiModelId = getModelIdValue('xai');

            const errorDiv = document.getElementById('api-keys-error');
            const successDiv = document.getElementById('api-keys-success');

            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';

            // Build combined payload for API keys and model IDs
            const payload = {};

            // Add API keys if provided
            if (geminiKey) payload.gemini_api_key = geminiKey;
            if (openaiKey) payload.openai_api_key = openaiKey;
            if (anthropicKey) payload.anthropic_api_key = anthropicKey;
            if (xaiKey) payload.xai_api_key = xaiKey;

            // Always include model IDs (even if empty to allow clearing)
            payload.gemini_model_id = geminiModelId;
            payload.openai_model_id = openaiModelId;
            payload.anthropic_model_id = anthropicModelId;
            payload.xai_model_id = xaiModelId;

            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (response.ok) {
                    successDiv.textContent = data.message || 'Settings saved successfully!';
                    successDiv.style.display = 'block';

                    // Clear API key input fields
                    document.getElementById('gemini-api-key').value = '';
                    document.getElementById('openai-api-key').value = '';
                    document.getElementById('anthropic-api-key').value = '';
                    document.getElementById('xai-api-key').value = '';

                    // Reload to update placeholders and model IDs
                    await loadAPIKeys();
                    await loadLocalModelSettings();

                    if (data.errors && data.errors.length > 0) {
                        errorDiv.innerHTML = '<strong>Some warnings:</strong><ul>' +
                            data.errors.map(err => '<li>' + err + '</li>').join('') +
                            '</ul>';
                        errorDiv.style.display = 'block';
                    }
                } else {
                    errorDiv.textContent = data.error || 'Failed to save settings';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Network error. Please try again.';
                errorDiv.style.display = 'block';
            }
        });
    }

    // Local Model Settings form submission (saved to /api/config)
    const localModelsForm = document.getElementById('local-models-form');
    if (localModelsForm) {
        localModelsForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const lmStudioUrl = document.getElementById('lm-studio-url').value.trim();
            const lmStudioModelId = getModelIdValue('lm_studio');
            const ollamaUrl = document.getElementById('ollama-url').value.trim();
            const ollamaModelId = getModelIdValue('ollama');

            const errorDiv = document.getElementById('local-models-error');
            const successDiv = document.getElementById('local-models-success');

            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';

            // Build payload for /api/config
            const payload = {
                lm_studio_url: lmStudioUrl,
                lm_studio_model_id: lmStudioModelId,
                ollama_url: ollamaUrl,
                ollama_model_id: ollamaModelId
            };

            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (response.ok) {
                    successDiv.textContent = data.message || 'Settings saved successfully!';
                    successDiv.style.display = 'block';

                    // Reload settings to show what was actually saved
                    await loadLocalModelSettings();

                    if (data.errors && data.errors.length > 0) {
                        errorDiv.innerHTML = '<strong>Some warnings:</strong><ul>' +
                            data.errors.map(err => '<li>' + err + '</li>').join('') +
                            '</ul>';
                        errorDiv.style.display = 'block';
                    }
                } else {
                    errorDiv.textContent = data.error || 'Failed to save settings';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'Network error. Please try again.';
                errorDiv.style.display = 'block';
            }
        });
    }
}

// ==========================================
// Rate Limit Settings (Admin Only)
// ==========================================

// Load Rate Limit Settings
async function loadRateLimitSettings() {
    if (!isAdmin) return;

    try {
        const response = await fetch('/api/admin/rate-limits');
        if (!response.ok) {
            console.error('Failed to load rate limit settings');
            return;
        }

        const data = await response.json();
        const rateLimits = data.rate_limits || {};

        // Set the toggle
        const enabledToggle = document.getElementById('rate-limit-enabled-toggle');
        if (enabledToggle) {
            enabledToggle.checked = rateLimits.enabled !== false;
            updateRateLimitFieldsVisibility(enabledToggle.checked);
        }

        // Set individual rate limits
        const fields = {
            'rate-limit-chat': rateLimits.chat,
            'rate-limit-attachment': rateLimits.attachment_upload,
            'rate-limit-document': rateLimits.document_upload,
            'rate-limit-improve-prompt': rateLimits.improve_prompt,
            'rate-limit-login': rateLimits.login,
            'rate-limit-register': rateLimits.register,
            'rate-limit-2fa': rateLimits['2fa']
        };

        for (const [id, value] of Object.entries(fields)) {
            const input = document.getElementById(id);
            if (input && value !== undefined) {
                input.value = value;
            }
        }
    } catch (error) {
        console.error('Error loading rate limit settings:', error);
    }
}

// Update visibility of rate limit input fields based on toggle state
function updateRateLimitFieldsVisibility(enabled) {
    const fieldsContainer = document.getElementById('rate-limit-fields');
    if (fieldsContainer) {
        fieldsContainer.style.opacity = enabled ? '1' : '0.5';
        fieldsContainer.style.pointerEvents = enabled ? 'auto' : 'none';
    }
}

// Setup Rate Limit Settings event listeners
function setupRateLimitListeners() {
    if (!isAdmin) return;

    // Enable/disable toggle
    const enabledToggle = document.getElementById('rate-limit-enabled-toggle');
    if (enabledToggle) {
        enabledToggle.addEventListener('change', (e) => {
            updateRateLimitFieldsVisibility(e.target.checked);
        });
    }

    // Save button
    const saveBtn = document.getElementById('save-rate-limits-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveRateLimitSettings);
    }
}

// Save Rate Limit Settings
async function saveRateLimitSettings() {
    const errorDiv = document.getElementById('rate-limits-error');
    const successDiv = document.getElementById('rate-limits-success');

    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';

    // Gather values
    const enabled = document.getElementById('rate-limit-enabled-toggle').checked;
    const chat = parseInt(document.getElementById('rate-limit-chat').value) || 100;
    const attachment = parseInt(document.getElementById('rate-limit-attachment').value) || 50;
    const document_upload = parseInt(document.getElementById('rate-limit-document').value) || 20;
    const improve_prompt = parseInt(document.getElementById('rate-limit-improve-prompt').value) || 30;
    const login = parseInt(document.getElementById('rate-limit-login').value) || 10;
    const register = parseInt(document.getElementById('rate-limit-register').value) || 5;
    const twofa = parseInt(document.getElementById('rate-limit-2fa').value) || 10;

    // Validate values
    const validationErrors = [];
    if (chat < 1 || chat > 10000) validationErrors.push('Chat rate limit must be between 1 and 10000');
    if (attachment < 1 || attachment > 10000) validationErrors.push('Attachment rate limit must be between 1 and 10000');
    if (document_upload < 1 || document_upload > 10000) validationErrors.push('Document rate limit must be between 1 and 10000');
    if (improve_prompt < 1 || improve_prompt > 10000) validationErrors.push('Prompt improvement rate limit must be between 1 and 10000');
    if (login < 1 || login > 10000) validationErrors.push('Login rate limit must be between 1 and 10000');
    if (register < 1 || register > 10000) validationErrors.push('Registration rate limit must be between 1 and 10000');
    if (twofa < 1 || twofa > 10000) validationErrors.push('2FA rate limit must be between 1 and 10000');

    if (validationErrors.length > 0) {
        errorDiv.innerHTML = validationErrors.join('<br>');
        errorDiv.style.display = 'block';
        return;
    }

    try {
        const response = await fetch('/api/admin/rate-limits', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                enabled: enabled,
                chat: chat,
                attachment_upload: attachment,
                document_upload: document_upload,
                improve_prompt: improve_prompt,
                login: login,
                register: register,
                '2fa': twofa
            })
        });

        const data = await response.json();

        if (response.ok) {
            successDiv.textContent = data.message || 'Rate limits saved successfully!';
            successDiv.style.display = 'block';

            setTimeout(() => {
                successDiv.style.display = 'none';
            }, 3000);

            // Reload to confirm values
            await loadRateLimitSettings();
        } else {
            errorDiv.textContent = data.error || 'Failed to save rate limits';
            errorDiv.style.display = 'block';

            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    } catch (error) {
        console.error('Error saving rate limit settings:', error);
        errorDiv.textContent = 'Network error. Please try again.';
        errorDiv.style.display = 'block';

        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
}


// ==========================================
// Child Safety Settings (Admin Only)
// ==========================================

// Load Child Safety Settings
async function loadChildSafetySettings() {
    if (!isAdmin) return;

    try {
        // Load child safety enabled toggle
        await loadBooleanSetting('child_safety_enabled', 'child-safety-toggle');

        // Load child system prompt
        const childPromptResponse = await fetch('/api/admin/settings/child_system_prompt');
        if (childPromptResponse.ok) {
            const childPromptData = await childPromptResponse.json();
            const childPromptTextarea = document.getElementById('child-system-prompt');
            if (childPromptTextarea && childPromptData.setting?.setting_value) {
                childPromptTextarea.value = childPromptData.setting.setting_value;
            }
        }

        // Load teen system prompt
        const teenPromptResponse = await fetch('/api/admin/settings/teen_system_prompt');
        if (teenPromptResponse.ok) {
            const teenPromptData = await teenPromptResponse.json();
            const teenPromptTextarea = document.getElementById('teen-system-prompt');
            if (teenPromptTextarea && teenPromptData.setting?.setting_value) {
                teenPromptTextarea.value = teenPromptData.setting.setting_value;
            }
        }
    } catch (error) {
        console.error('Error loading child safety settings:', error);
    }
}

// Setup Child Safety Settings event listeners
function setupChildSafetyListeners() {
    if (!isAdmin) return;

    // Child safety toggle
    const childSafetyToggle = document.getElementById('child-safety-toggle');
    if (childSafetyToggle) {
        childSafetyToggle.addEventListener('change', async (e) => {
            const enabled = e.target.checked;
            await updateAdminSetting('child_safety_enabled', enabled);
        });
    }

    // Use Default button for child prompt
    const childDefaultBtn = document.getElementById('child-prompt-default-btn');
    if (childDefaultBtn) {
        childDefaultBtn.addEventListener('click', () => {
            const textarea = document.getElementById('child-system-prompt');
            if (textarea) {
                textarea.value = DEFAULT_CHILD_PROMPT;
            }
        });
    }

    // Use Default button for teen prompt
    const teenDefaultBtn = document.getElementById('teen-prompt-default-btn');
    if (teenDefaultBtn) {
        teenDefaultBtn.addEventListener('click', () => {
            const textarea = document.getElementById('teen-system-prompt');
            if (textarea) {
                textarea.value = DEFAULT_TEEN_PROMPT;
            }
        });
    }

    // Save child safety settings button
    const saveBtn = document.getElementById('save-child-safety-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            const childPrompt = document.getElementById('child-system-prompt').value;
            const teenPrompt = document.getElementById('teen-system-prompt').value;

            const errorDiv = document.getElementById('child-safety-error');
            const successDiv = document.getElementById('child-safety-success');

            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';

            try {
                // Save child system prompt
                const childResponse = await fetch('/api/admin/settings/child_system_prompt', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        value: childPrompt,
                        setting_type: 'string'
                    })
                });

                if (!childResponse.ok) {
                    throw new Error('Failed to save child system prompt');
                }

                // Save teen system prompt
                const teenResponse = await fetch('/api/admin/settings/teen_system_prompt', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        value: teenPrompt,
                        setting_type: 'string'
                    })
                });

                if (!teenResponse.ok) {
                    throw new Error('Failed to save teen system prompt');
                }

                successDiv.textContent = 'Child safety settings saved successfully!';
                successDiv.style.display = 'block';

                setTimeout(() => {
                    successDiv.style.display = 'none';
                }, 3000);

            } catch (error) {
                console.error('Error saving child safety settings:', error);
                errorDiv.textContent = 'Failed to save child safety settings. Please try again.';
                errorDiv.style.display = 'block';

                setTimeout(() => {
                    errorDiv.style.display = 'none';
                }, 5000);
            }
        });
    }
}
