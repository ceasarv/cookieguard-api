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
    .cg-modal {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.55);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 999999;
    }
    
    /* Modal container */
    .cg-hub-container {
        background: white;
        width: 90%;
        max-width: 640px;
        max-height: 85vh;
        overflow-y: auto;
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 18px 40px rgba(0,0,0,.25);
        animation: fadeIn .25s ease;
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
    
    /* iOS toggle switch */
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
    
    /* Buttons */
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
        <div class="cg-left">
          <div class="cg-title">${cfg.title}</div>
          <div class="cg-desc">${cfg.description}</div>
        </div>

        <div class="cg-right">
          <div class="cg-buttons">
            <button class="cg-btn cg-accept">${cfg.accept_text}</button>
            <button class="cg-btn cg-reject">${cfg.reject_text}</button>
            ${cfg.show_prefs ? `<button class="cg-btn cg-prefs">${cfg.prefs_text}</button>` : ""}
          </div>
        </div>
      </div>

      ${cfg.show_logo ? `
        <div class="cg-footer">
          <a href='https://cookieguard.app' target='_blank' rel='noopener noreferrer'>
            Powered by CookieGuard
          </a>
        </div>` : ""}
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
