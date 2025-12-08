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

    // --- Shadow root host ---
    const host = document.createElement("div");
    host.style.position = "fixed";
    host.style.zIndex = "999999";
    host.style.bottom = "0";
    host.style.left = "0";
    host.style.width = "100vw";
    host.style.margin = "0";
    document.body.appendChild(host);

    const shadow = host.attachShadow({mode: "open"});

    // --- Styles ---
    const style = document.createElement("style");
    style.textContent = `
    .cg-wrap {
        font-family: system-ui, sans-serif;
        line-height: 1.45;
        animation: cgFadeIn 0.3s ease;
    }

    .cg-bar {
        background: ${cfg.background_color};
        color: ${cfg.text_color};
        border-radius: ${cfg.border_radius_px}px;
        padding: 20px 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 20px;
        max-width: 100%;
    }

    .cg-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .cg-title {
        font-weight: 700;
        font-size: 1.05rem;
    }

    .cg-desc {
        font-size: 0.95rem;
        max-width: 600px;
    }

    .cg-buttons {
        display: flex;
        gap: ${cfg.spacing_px}px;
        flex-wrap: wrap;
    }

    .cg-btn {
        cursor: pointer;
        padding: 10px 18px;
        border: none;
        border-radius: 6px;
        font-size: 0.9rem;
        font-weight: 500;
        transition: opacity 0.15s ease;
    }

    .cg-btn:hover {
        opacity: 0.85;
    }

    .cg-accept {
        background: ${cfg.accept_bg_color};
        color: ${cfg.accept_text_color};
    }

    .cg-reject {
        background: ${cfg.reject_bg_color};
        color: ${cfg.reject_text_color};
    }

    .cg-prefs {
        background: ${cfg.prefs_bg_color};
        color: ${cfg.prefs_text_color};
    }

    .cg-footer {
        font-size: 12px;
        opacity: 0.5;
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
        width: 90%;
        max-width: 640px;
        max-height: 85vh;
        overflow-y: auto;
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 18px 40px rgba(0,0,0,.25);
        animation: cgFadeIn .25s ease;
    }
    
    .cg-hub-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
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
        opacity: .6;
    }
    .cg-tab.active {
        opacity: 1;
        font-weight: 600;
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
        align-items: center;
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
        display: flex;
        justify-content: flex-end;
    }
    .cg-save-btn {
        background: ${cfg.accept_bg_color};
        color: white;
        padding: 12px 18px;
        border-radius: 8px;
        cursor: pointer;
        border: none;
        font-weight: 600;
    }
    .cg-save-btn:hover { opacity: .9; }
    `;

    // --- Banner HTML ---
    const box = document.createElement("div");
    box.className = "cg-wrap";
    box.innerHTML = `
      <div class="cg-bar">
        <div class="cg-content">
          <div class="cg-title">${cfg.title}</div>
          <div class="cg-desc">${cfg.description}</div>
          <div class="cg-buttons">
            <button class="cg-btn cg-accept">${cfg.accept_text}</button>
            <button class="cg-btn cg-reject">${cfg.reject_text}</button>
            ${cfg.show_prefs ? `<button class="cg-btn cg-prefs">${cfg.prefs_text}</button>` : ""}
          </div>
        </div>

        ${cfg.show_logo ? `
        <div class="cg-footer">
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
        logConsent("accept_all");
        host.remove();
    };

    shadow.querySelector(".cg-reject").onclick = () => {
        logConsent("reject_all");
        host.remove();
    };

    const prefsBtn = shadow.querySelector(".cg-prefs");

    if (prefsBtn) {
        prefsBtn.onclick = () => {
            loadPrefsModule();
        };
    }

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

})();