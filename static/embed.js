(function () {
    const cfg = window.CookieGuardConfig || {};
    if (!cfg.id) {
        console.warn("[CookieGuard] No config found");
        return;
    }

    console.log("[CookieGuard DEBUG] Loaded config:", window.CookieGuardConfig);
    console.log("[CookieGuard] ✅ Banner loaded:", cfg);

    function logConsent(choice, prefs = null) {
        const payload = {
            embed_key: cfg.embed_key,
            banner_id: cfg.id,
            banner_version: 1,
            choice,
            preferences: prefs,
        };
        fetch(cfg.api_url, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        })
            .then(res => res.json())
            .then(data => console.log("[CookieGuard] Consent logged:", data))
            .catch(err => console.warn("[CookieGuard] log failed:", err));
    }

    // --- Cookie Blocking System ---
    const CookieGuardBlocker = {
        getConsent: function() {
            const stored = localStorage.getItem('cookieguard_consent_' + cfg.embed_key);
            return stored ? JSON.parse(stored) : null;
        },

        setConsent: function(choice, prefs = null) {
            const consent = {
                choice: choice,
                preferences: prefs,
                timestamp: new Date().toISOString()
            };
            localStorage.setItem('cookieguard_consent_' + cfg.embed_key, JSON.stringify(consent));
            return consent;
        },

        hasConsent: function(category) {
            const consent = this.getConsent();
            if (!consent) return false;

            if (consent.choice === 'accept_all') return true;
            if (consent.choice === 'reject_all') return category === 'necessary';
            if (consent.choice === 'preferences_saved' && consent.preferences) {
                return consent.preferences[category] === true;
            }
            return false;
        },

        blockScripts: function() {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.tagName === 'SCRIPT' && node.hasAttribute('data-cookiecategory')) {
                            const category = node.getAttribute('data-cookiecategory');
                            if (!this.hasConsent(category)) {
                                node.type = 'text/plain';
                                node.setAttribute('data-blocked', 'true');
                            }
                        }
                    });
                });
            });

            observer.observe(document.documentElement, {
                childList: true,
                subtree: true
            });

            // Block existing scripts
            document.addEventListener('DOMContentLoaded', () => {
                const scripts = document.querySelectorAll('script[data-cookiecategory]');
                scripts.forEach(script => {
                    const category = script.getAttribute('data-cookiecategory');
                    if (!this.hasConsent(category)) {
                        script.type = 'text/plain';
                        script.setAttribute('data-blocked', 'true');
                    }
                });
            });
        },

        enableScripts: function(categories) {
            const blockedScripts = document.querySelectorAll('script[data-blocked="true"]');
            blockedScripts.forEach(script => {
                const category = script.getAttribute('data-cookiecategory');

                if (categories.includes(category)) {
                    script.type = 'text/javascript';
                    script.removeAttribute('data-blocked');

                    // Clone and replace to execute
                    const newScript = document.createElement('script');
                    Array.from(script.attributes).forEach(attr => {
                        newScript.setAttribute(attr.name, attr.value);
                    });
                    newScript.textContent = script.textContent;
                    if (script.src) newScript.src = script.src;
                    script.parentNode.replaceChild(newScript, script);
                }
            });
        },

        deleteCookies: function(categories) {
            if (!cfg.categories) return;

            categories.forEach(category => {
                const patterns = cfg.categories[category] || [];
                patterns.forEach(item => {
                    this.deleteCookiesByPattern(item.pattern);
                });
            });
        },

        deleteCookiesByPattern: function(pattern) {
            const cookies = document.cookie.split(';');
            cookies.forEach(cookie => {
                const cookieName = cookie.split('=')[0].trim();
                if (cookieName.includes(pattern) || pattern.includes(cookieName)) {
                    document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
                    document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.${window.location.hostname}`;
                }
            });
        }
    };

    // Expose blocker for prefs.js
    window.CookieGuardBlocker = CookieGuardBlocker;

    // Start blocking scripts immediately
    CookieGuardBlocker.blockScripts();

    // --- Global state ---
    let host = null;
    let shadow = null;
    let box = null;

    // --- Banner creation function ---
    function createBanner() {
        // Remove existing banner if present
        if (host && host.parentNode) {
            host.remove();
        }

        // --- Shadow root host ---
        host = document.createElement("div");
        host.style.position = "fixed";
        host.style.zIndex = cfg.z_index || "999999";
        host.style.margin = "0";

        // Position based on type and position
        const type = cfg.type || "bar";
        const position = cfg.position || "bottom";

        if (type === "modal") {
            // Modal: centered
            host.style.inset = "0";
            host.style.display = "flex";
            host.style.alignItems = "center";
            host.style.justifyContent = "center";
        } else if (type === "bar") {
            // Bar: full width at top or bottom
            host.style.left = "0";
            host.style.right = "0";
            host.style.width = "100%";
            if (position === "top") {
                host.style.top = "0";
            } else {
                host.style.bottom = "0";
            }
        } else if (type === "panel") {
            // Panel: positioned in corner or side
            const gap = "20px"; // Gap from edges

            if (position === "bottom-left") {
                host.style.bottom = gap;
                host.style.left = gap;
            } else if (position === "bottom-right") {
                host.style.bottom = gap;
                host.style.right = gap;
            } else if (position === "top-left") {
                host.style.top = gap;
                host.style.left = gap;
            } else if (position === "top-right") {
                host.style.top = gap;
                host.style.right = gap;
            } else if (position === "bottom") {
                host.style.bottom = gap;
                host.style.left = "50%";
                host.style.transform = "translateX(-50%)";
            } else if (position === "top") {
                host.style.top = gap;
                host.style.left = "50%";
                host.style.transform = "translateX(-50%)";
            } else if (position === "center") {
                host.style.top = "50%";
                host.style.left = "50%";
                host.style.transform = "translate(-50%, -50%)";
            }
        }

        document.body.appendChild(host);

        shadow = host.attachShadow({mode: "open"});

        // --- Shadow helper ---
        function getShadow(shadowType) {
            const shadows = {
                'none': 'none',
                'sm': '0 1px 2px rgba(0,0,0,0.05)',
                'md': '0 4px 6px rgba(0,0,0,0.1)',
                'lg': '0 10px 15px rgba(0,0,0,0.1)',
                'xl': '0 20px 25px rgba(0,0,0,0.15)',
            };
            return shadows[shadowType] || shadows['md'];
        }

        // --- Styles ---
        const style = document.createElement("style");
        style.textContent = `
    *, *::before, *::after {
        box-sizing: border-box;
    }

    .cg-wrap {
        font-family: system-ui, sans-serif;
        line-height: 1.45;
        animation: cgFadeIn 0.3s ease;
    }

    .cg-bar {
        background: ${cfg.background_color};
        opacity: ${cfg.background_opacity};
        color: ${cfg.text_color || '#111827'};
        border-radius: ${cfg.border_radius_px}px;
        border: ${cfg.border_width_px}px solid ${cfg.border_color};
        padding: ${cfg.padding_y_px + 8}px ${cfg.padding_x_px}px;
        box-shadow: ${cfg.shadow_custom || getShadow(cfg.shadow)};
        position: relative;
        padding-bottom: 40px;
        ${cfg.type === 'panel' ? `
            max-width: 420px;
            width: 100%;
        ` : cfg.type === 'modal' ? `
            max-width: 650px;
            width: 90%;
            margin: 0 auto;
        ` : `
            max-width: 1000px;
            width: 100%;
            margin: 0 auto;
        `}
    }

    .cg-left {
        width: 100%;
    }

    .cg-title {
        font-weight: 700;
        font-size: 1.05rem;
        margin-bottom: 6px;
    }

    .cg-desc {
        font-size: 0.95rem;
        max-width: 600px;
        margin-bottom: ${cfg.spacing_px}px;
    }

    .cg-buttons {
        display: flex;
        gap: ${cfg.spacing_px}px;
        flex-wrap: wrap;
        margin-top: ${cfg.spacing_px}px;
    }

    .cg-btn {
        cursor: pointer;
        padding: 10px 18px;
        font-size: 0.9rem;
        font-weight: 500;
        transition: opacity 0.15s ease;
        border: 1px solid transparent;
    }

    .cg-btn:hover {
        opacity: 0.85;
    }

    .cg-accept {
        background: ${cfg.accept_bg_color};
        color: ${cfg.accept_text_color};
        border: ${cfg.accept_border_width_px}px solid ${cfg.accept_border_color};
        border-radius: ${cfg.accept_border_radius_px}px;
    }

    .cg-reject {
        background: ${cfg.reject_bg_color};
        color: ${cfg.reject_text_color};
        border: ${cfg.reject_border_width_px}px solid ${cfg.reject_border_color};
        border-radius: ${cfg.reject_border_radius_px}px;
    }

    .cg-prefs {
        background: ${cfg.prefs_bg_color};
        color: ${cfg.prefs_text_color};
        border: ${cfg.prefs_border_width_px}px solid ${cfg.prefs_border_color};
        border-radius: ${cfg.prefs_border_radius_px}px;
    }

    .cg-footer {
        position: absolute;
        bottom: 8px;
        right: 12px;
        font-size: 11px;
        opacity: 0.6;
        white-space: nowrap;
    }

    .cg-footer a {
        color: inherit;
        text-decoration: none;
    }

    .cg-footer a:hover {
        text-decoration: underline;
        opacity: 1;
    }

    @keyframes cgFadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Responsive adjustments */
    @media (max-width: 640px) {
        .cg-bar {
            ${cfg.type === 'panel' ? `
                max-width: calc(100vw - 40px) !important;
            ` : ''}
        }
        .cg-desc {
            font-size: 0.85rem;
        }
        .cg-buttons {
            flex-direction: column;
        }
        .cg-btn {
            width: 100%;
            text-align: center;
        }
    }

    /* Overlay */
    .cg-overlay {
        position: fixed;
        inset: 0;
        background: ${cfg.overlay_color};
        opacity: ${cfg.overlay_opacity};
        backdrop-filter: blur(${cfg.overlay_blur_px}px);
        ${cfg.type === 'modal' ? 'z-index: 1;' : 'z-index: -1;'}
    }

    /* For modal type, ensure banner is above overlay */
    ${cfg.type === 'modal' ? `
        .cg-bar {
            position: relative;
            z-index: 2;
        }
    ` : ''}

    /* Modal styles */
    .cg-modal {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.55);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 999999;
    }
    
    .cg-hub-container {
        background: white;
        color: #111827;
        width: 90%;
        max-width: 640px;
        max-height: 85vh;
        overflow-y: auto;
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 18px 40px rgba(0,0,0,.25);
        animation: cgFadeIn .25s ease;
    }

    .cg-hub-container h2 {
        color: #111827;
        font-size: 1.5rem;
        font-weight: 600;
    }

    .cg-hub-container h3 {
        color: #111827;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .cg-hub-container p {
        color: #6b7280;
        font-size: 0.9rem;
        line-height: 1.5;
        margin: 0;
    }

    .cg-hub-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    
    .cg-close {
        font-size: 1.7rem;
        background: none;
        border: none;
        cursor: pointer;
        opacity: .5;
    }
    .cg-close:hover { opacity: .9; }
    
    .cg-hub-tabs {
        margin-top: 20px;
        display: flex;
        gap: 10px;
        border-bottom: 1px solid #ddd;
    }
    
    .cg-tab {
        border: none;
        background: none;
        padding: 10px 6px;
        cursor: pointer;
        font-size: .95rem;
        color: #374151;
        opacity: .6;
    }
    .cg-tab.active {
        opacity: 1;
        font-weight: 600;
        color: #111827;
        border-bottom: 2px solid #333;
    }
    
    .cg-tab-panel.hidden { display: none; }
    
    .cg-category {
        margin-top: 20px;
        padding-bottom: 15px;
        border-bottom: 1px solid #eee;
    }
    
    .cg-cat-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
    }

    .cg-cat-row > div:first-child {
        flex: 1;
    }

    .cg-cat-row h3 {
        margin: 0 0 4px 0;
        color: #111827;
        font-size: 1rem;
        font-weight: 600;
    }

    .cg-cat-row p {
        margin: 0;
        color: #6b7280;
        font-size: 0.85rem;
    }
    
    .cg-switch {
        position: relative;
        width: 46px;
        height: 24px;
    }
    .cg-switch input {
        display: none;
    }
    .cg-slider {
        position: absolute;
        inset: 0;
        border-radius: 24px;
        background: #ccc;
        cursor: pointer;
        transition: .2s;
    }
    .cg-slider::before {
        content: "";
        position: absolute;
        width: 18px;
        height: 18px;
        top: 3px;
        left: 3px;
        border-radius: 50%;
        background: white;
        transition: .2s;
    }
    .cg-switch input:checked + .cg-slider {
        background: ${cfg.accept_bg_color};
    }
    .cg-switch input:checked + .cg-slider::before {
        transform: translateX(22px);
    }
    
    .cg-hub-footer {
        margin-top: 20px;
    }
    .cg-hub-footer-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .cg-prefs-logo {
        font-size: 0.75rem;
        color: #6b7280;
        text-decoration: none;
        transition: color 0.2s;
    }
    .cg-prefs-logo:hover {
        color: #111827;
    }
    .cg-prefs-logo strong {
        font-weight: 600;
    }
    .cg-save-btn {
        background: ${cfg.accept_bg_color};
        color: ${cfg.accept_text_color};
        padding: 12px 18px;
        border-radius: ${cfg.accept_border_radius_px}px;
        cursor: pointer;
        border: ${cfg.accept_border_width_px}px solid ${cfg.accept_border_color};
        font-weight: 600;
    }
    .cg-save-btn:hover { opacity: .9; }
    `;

        // --- Banner HTML ---
        box = document.createElement("div");
        box.className = "cg-wrap";
        box.innerHTML = `
      ${cfg.overlay_enabled ? `<div class="cg-overlay"></div>` : ""}
      <div class="cg-bar">
        <div class="cg-left">
          <div class="cg-title">${cfg.title}</div>
          <div class="cg-desc">${cfg.description}</div>
          <div class="cg-buttons">
            <button class="cg-btn cg-accept">${cfg.accept_text}</button>
            ${cfg.has_reject_button ? `<button class="cg-btn cg-reject">${cfg.reject_text}</button>` : ""}
            ${cfg.show_prefs ? `<button class="cg-btn cg-prefs">${cfg.prefs_text}</button>` : ""}
          </div>
        </div>

        ${cfg.show_logo ? `<div class="cg-footer">
          <a href='https://cookieguard.app' target='_blank' rel='noopener noreferrer'>
            Powered by CookieGuard
          </a>
        </div>` : ""}
      </div>
    `;

        shadow.appendChild(style);
        shadow.appendChild(box);

        // --- Event handling ---
        shadow.querySelector(".cg-accept").onclick = () => {
            CookieGuardBlocker.setConsent("accept_all");
            CookieGuardBlocker.enableScripts(['necessary', 'preferences', 'analytics', 'marketing']);
            logConsent("accept_all");
            host.remove();
        };

        const rejectBtn = shadow.querySelector(".cg-reject");
        if (rejectBtn) {
            rejectBtn.onclick = () => {
                CookieGuardBlocker.setConsent("reject_all");
                CookieGuardBlocker.enableScripts(['necessary']);
                CookieGuardBlocker.deleteCookies(['preferences', 'analytics', 'marketing']);
                logConsent("reject_all");
                host.remove();
            };
        }

        const prefsBtn = shadow.querySelector(".cg-prefs");
        if (prefsBtn) {
            prefsBtn.onclick = () => {
                loadPrefsModule();
            };
        }
    }

    // --- Load preferences module ---
    function loadPrefsModule() {
        if (window.CookieGuardPrefsLoaded) {
            window.CookieGuardOpenPrefs(cfg, shadow, box, logConsent);
            return;
        }

        const s = document.createElement("script");
        s.src = "https://api.cookieguard.app/static/prefs.js";
        s.onload = () => {
            window.CookieGuardPrefsLoaded = true;
            window.CookieGuardOpenPrefs(cfg, shadow, box, logConsent);
        };
        document.head.appendChild(s);
    }

    // --- Public API Functions ---
    function openPreferences() {
        if (!shadow || !box) {
            console.warn("[CookieGuard] Cannot open preferences - banner not initialized");
            return;
        }
        loadPrefsModule();
    }

    function reopenBanner() {
        createBanner();
    }

    function clearConsent() {
        localStorage.removeItem('cookieguard_consent_' + cfg.embed_key);
        console.log("[CookieGuard] Consent cleared");
    }

    function updateConsent(choice, prefs = null) {
        CookieGuardBlocker.setConsent(choice, prefs);

        if (choice === 'accept_all') {
            CookieGuardBlocker.enableScripts(['necessary', 'preferences', 'analytics', 'marketing']);
        } else if (choice === 'reject_all') {
            CookieGuardBlocker.enableScripts(['necessary']);
            CookieGuardBlocker.deleteCookies(['preferences', 'analytics', 'marketing']);
        } else if (choice === 'preferences_saved' && prefs) {
            const enabledCategories = ['necessary'];
            Object.keys(prefs).forEach(cat => {
                if (prefs[cat]) enabledCategories.push(cat);
            });
            CookieGuardBlocker.enableScripts(enabledCategories);

            const rejectedCategories = Object.keys(prefs).filter(cat => !prefs[cat]);
            CookieGuardBlocker.deleteCookies(rejectedCategories);
        }

        logConsent(choice, prefs);

        // Close banner if open
        if (host && host.parentNode) {
            host.remove();
        }
    }

    // --- Expose global API ---
    window.CookieGuard = {
        hasConsent: (category) => CookieGuardBlocker.hasConsent(category),
        getConsent: () => CookieGuardBlocker.getConsent(),
        openPreferences: openPreferences,
        reopenBanner: reopenBanner,
        clearConsent: clearConsent,
        updateConsent: updateConsent
    };

    // --- Initialize ---
    const existingConsent = CookieGuardBlocker.getConsent();
    if (!existingConsent) {
        // No consent yet - show banner
        createBanner();
    } else {
        console.log("[CookieGuard] Existing consent found:", existingConsent);

        // Enable scripts based on existing consent
        if (existingConsent.choice === 'accept_all') {
            CookieGuardBlocker.enableScripts(['necessary', 'preferences', 'analytics', 'marketing']);
        } else if (existingConsent.choice === 'reject_all') {
            CookieGuardBlocker.enableScripts(['necessary']);
        } else if (existingConsent.choice === 'preferences_saved' && existingConsent.preferences) {
            const enabledCategories = ['necessary'];
            Object.keys(existingConsent.preferences).forEach(cat => {
                if (existingConsent.preferences[cat]) enabledCategories.push(cat);
            });
            CookieGuardBlocker.enableScripts(enabledCategories);
        }
    }

})();