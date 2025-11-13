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
        background: ${cfg.background_color};
        color: ${cfg.text_color};
        border-radius: 0;
        padding: ${cfg.spacing_px * 2}px;
        font-family: system-ui, sans-serif;
        width: 100%;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.15);
        box-sizing: border-box;
    }

    /* Bar Layout */
    .cg-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 24px;
    }

    .cg-left {
        flex: 1;
        min-width: 200px;
    }

    .cg-title {
        font-weight: 700;
        font-size: 1.05rem;
        margin-bottom: 4px;
    }

    .cg-desc {
        font-size: .92rem;
        line-height: 1.45;
        opacity: .9;
    }

    .cg-right {
        display: flex;
        align-items: center;
    }

    .cg-buttons {
        display: flex;
        gap: ${cfg.spacing_px}px;
        flex-wrap: nowrap;
    }

    .cg-btn {
        cursor: pointer;
        padding: 10px 16px;
        border-radius: ${cfg.border_radius_px}px;
        font-size: .9rem;
        font-weight: 600;
        border: none;
        white-space: nowrap;
        transition: .15s ease;
    }

    .cg-btn:hover {
        opacity: .9;
        transform: translateY(-1px);
    }

    .cg-accept { background: ${cfg.accept_bg_color}; color: ${cfg.accept_text_color}; }
    .cg-reject { background: ${cfg.reject_bg_color}; color: ${cfg.reject_text_color}; border: 1px solid rgba(0,0,0,.1); }
    .cg-prefs  { background: ${cfg.prefs_bg_color}; color: ${cfg.prefs_text_color}; border: 1px solid rgba(0,0,0,.1); }

    .cg-footer {
        margin-top: 6px;
        text-align: right;
        font-size: 11px;
        opacity: .65;
    }
    .cg-footer a:hover {
        opacity: 1;
        text-decoration: underline;
    }

    /* Modal styling */
    .cg-modal {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.55);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 999999;
        animation: fadeIn .2s ease-out;
    }

    @keyframes fadeIn {
        from { opacity: 0 }
        to   { opacity: 1 }
    }

    .cg-modal-content {
        background: #fff;
        padding: 24px;
        border-radius: 12px;
        width: 100%;
        max-width: 420px;
        box-shadow: 0 15px 30px rgba(0,0,0,.2);
        animation: popIn .25s cubic-bezier(.2,1.1,.4,1);
    }

    @keyframes popIn {
        from { transform: scale(.93); opacity: 0 }
        to   { transform: scale(1); opacity: 1 }
    }

    .cg-option {
        display: flex;
        justify-content: space-between;
        padding: 10px 0;
        font-size: .95rem;
        border-bottom: 1px solid #eee;
    }

    .cg-modal-actions {
        display: flex;
        justify-content: flex-end;
        margin-top: 20px;
        gap: 10px;
    }
    .cg-save {
        background: ${cfg.accept_bg_color};
        color: ${cfg.accept_text_color};
        padding: 10px 18px;
        border-radius: 6px;
        border: none;
        cursor: pointer;
    }
    .cg-cancel {
        background: transparent;
        color: #555;
        padding: 10px 14px;
        border: none;
        cursor: pointer;
    }

    /* Mobile layout */
    @media (max-width: 640px) {
        .cg-bar {
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
        }
        .cg-buttons {
            flex-wrap: wrap;
            justify-content: flex-start;
        }
    }
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

    // --- Modular prefs loader ---
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
