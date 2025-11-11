(function () {
    const cfg = window.CookieGuardConfig || {};
    if (!cfg.id) {
        console.warn("[CookieGuard] No config found");
        return;
    }

    console.log("[CookieGuard] ✅ Banner loaded:", cfg);

    function logConsent(choice, prefs = null) {
        const payload = {
            embed_key: cfg.id,
            banner_id: cfg.id,
            banner_version: 1,
            choice,
            preferences: prefs,
        };
        fetch(cfg.api_url, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        }).catch((err) => console.warn("[CookieGuard] log failed", err));
    }

    // --- create shadow root host ---
    const host = document.createElement("div");
    host.style.position = "fixed";
    host.style.zIndex = "9999";
    host.style.bottom = "20px";
    host.style.left = "20px";
    document.body.appendChild(host);

    const shadow = host.attachShadow({mode: "open"});

    // --- style ---
    const style = document.createElement("style");
    style.textContent = `
    .cg-wrap {
      background: ${cfg.background_color};
      color: ${cfg.text_color};
      border-radius: ${cfg.border_radius_px}px;
      padding: 16px;
      max-width: 420px;
      font-family: system-ui,sans-serif;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      position: relative;
    }
    .cg-buttons {
      display: flex;
      gap: ${cfg.spacing_px}px;
      justify-content: center;
      flex-wrap: wrap;
    }
    .cg-btn {
      cursor: pointer;
      padding: 8px 14px;
      border: none;
      border-radius: 6px;
      font-size: .9rem;
      transition: opacity .15s ease;
    }
    .cg-btn:hover { opacity: 0.85; }
    .cg-accept { background: ${cfg.accept_bg_color}; color: ${cfg.accept_text_color}; }
    .cg-reject { background: ${cfg.reject_bg_color}; color: ${cfg.reject_text_color}; }
    .cg-prefs { background: ${cfg.prefs_bg_color}; color: ${cfg.prefs_text_color}; }
    .cg-footer {
      margin-top: 8px;
      font-size: 11px;
      opacity: .6;
      text-align: right;
    }
    .cg-footer a {
      color: inherit;
      text-decoration: none;
    }
    .cg-footer a:hover {
      text-decoration: underline;
      opacity: 1;
    }
    .cg-modal {
      position: absolute;
      inset: 0;
      background: rgba(0,0,0,0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: inherit;
      z-index: 999999;
    }
    .cg-modal-content {
      background: #fff;
      color: #111;
      padding: 20px;
      border-radius: 10px;
      max-width: 360px;
      width: 100%;
      box-shadow: 0 10px 25px rgba(0,0,0,0.25);
    }
    .cg-toggle-row {
      display: flex;
      justify-content: space-between;
      margin: 10px 0;
    }
  `;

    // --- main banner HTML ---
    const box = document.createElement("div");
    box.className = "cg-wrap";
    box.innerHTML = `
    <div class="cg-title" style="font-weight:700;margin-bottom:6px;">${cfg.title}</div>
    <div class="cg-desc" style="font-size:0.95rem;margin-bottom:${cfg.spacing_px}px;">${cfg.description}</div>
    <div class="cg-buttons">
      <button class="cg-btn cg-accept">${cfg.accept_text}</button>
      <button class="cg-btn cg-reject">${cfg.reject_text}</button>
      ${cfg.show_prefs ? `<button class="cg-btn cg-prefs">${cfg.prefs_text}</button>` : ""}
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
