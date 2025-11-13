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


    // --- create shadow root host ---
    const host = document.createElement("div");
    host.style.position = "fixed";
    host.style.zIndex = "999999";
    host.style.bottom = "0";
    host.style.left = "0";
    host.style.width = "100vw";
    host.style.margin = "0";
    document.body.appendChild(host);

    const shadow = host.attachShadow({mode: "open"});

    // --- style ---
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
    
    /* Horizontal layout */
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
    
    /* Right-buttons layout */
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
    
    /* Button colors */
    .cg-accept { background: ${cfg.accept_bg_color}; color: ${cfg.accept_text_color}; }
    .cg-reject { background: ${cfg.reject_bg_color}; color: ${cfg.reject_text_color}; border: 1px solid rgba(0,0,0,.1); }
    .cg-prefs  { background: ${cfg.prefs_bg_color}; color: ${cfg.prefs_text_color}; border: 1px solid rgba(0,0,0,.1); }
    
    /* Footer */
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
    }`;

    // --- main banner HTML ---
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

    // --- event handling ---
    const acceptBtn = shadow.querySelector(".cg-accept");
    const rejectBtn = shadow.querySelector(".cg-reject");
    const prefsBtn = shadow.querySelector(".cg-prefs");

    acceptBtn.onclick = () => {
        logConsent("accept_all");
        host.remove();
    };
    rejectBtn.onclick = () => {
        logConsent("reject_all");
        host.remove();
    };

    if (prefsBtn) {
        prefsBtn.onclick = () => {
            const modal = document.createElement("div");
            modal.className = "cg-modal";
            modal.innerHTML = `
        <div class="cg-modal-content">
          <h3 style="margin-bottom:10px;">Cookie Preferences</h3>
          <div class="cg-toggle-row"><span>Necessary</span><input type="checkbox" checked disabled /></div>
          <div class="cg-toggle-row"><span>Analytics</span><input id="cg-analytics" type="checkbox" /></div>
          <div class="cg-toggle-row"><span>Marketing</span><input id="cg-marketing" type="checkbox" /></div>
          <div style="margin-top:16px;text-align:right;">
            <button id="cg-save-prefs" class="cg-btn cg-accept">${cfg.prefs_text || "Save"}</button>
          </div>
        </div>
      `;
            box.appendChild(modal);
            modal.querySelector("#cg-save-prefs").onclick = () => {
                const prefs = {
                    analytics: modal.querySelector("#cg-analytics").checked,
                    marketing: modal.querySelector("#cg-marketing").checked,
                };
                localStorage.setItem("cookieguard_prefs", JSON.stringify(prefs));
                logConsent("preferences_saved", prefs);
                modal.remove();
                host.remove();
            };
        };
    }
})();
