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
    padding: ${cfg.spacing_px * 2}px;
    font-family: system-ui, sans-serif;
    box-shadow: 0 6px 20px rgba(0,0,0,0.18);
    position: relative;
    width: 100%;
    max-width: 860px;
    animation: cg-slide-up .45s cubic-bezier(0.25, 1, 0.5, 1);
    display: flex;
    flex-direction: column;
    gap: ${cfg.spacing_px * 1.5}px;
  }

  @keyframes cg-slide-up {
    from { transform: translateY(30px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  .cg-title {
    font-weight: 700;
    font-size: 1.05rem;
    line-height: 1.4;
  }

  .cg-desc {
    font-size: 0.92rem;
    line-height: 1.45;
    opacity: .9;
  }

  .cg-buttons {
    display: flex;
    gap: ${cfg.spacing_px}px;
    flex-wrap: wrap;
    justify-content: ${cfg.text_align === "center" ? "center" : cfg.text_align === "right" ? "flex-end" : "flex-start"};
  }

  .cg-btn {
    cursor: pointer;
    padding: 10px 18px;
    border: none;
    border-radius: ${cfg.border_radius_px}px;
    font-size: .9rem;
    font-weight: 600;
    transition: transform .15s ease, opacity .15s ease;
    min-width: 110px;
  }

  .cg-btn:hover {
    opacity: .9;
    transform: translateY(-1px);
  }

  .cg-accept {
    background: ${cfg.accept_bg_color};
    color: ${cfg.accept_text_color};
  }
  
  .cg-reject {
    background: ${cfg.reject_bg_color};
    color: ${cfg.reject_text_color};
    border: 1px solid rgba(0,0,0,0.1);
  }

  .cg-prefs {
    background: ${cfg.prefs_bg_color};
    color: ${cfg.prefs_text_color};
    border: 1px solid rgba(0,0,0,0.1);
  }

  .cg-footer {
    margin-top: 4px;
    font-size: 11px;
    opacity: .65;
    text-align: right;
  }

  .cg-footer a {
    color: inherit;
    text-decoration: none;
  }
  .cg-footer a:hover {
    opacity: 1;
    text-decoration: underline;
  }

  /* Modal */
  .cg-modal {
    position: absolute;
    inset: 0;
    background: rgba(0,0,0,0.55);
    backdrop-filter: blur(3px);
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: inherit;
    padding: 20px;
    z-index: 999999;
  }

  .cg-modal-content {
    background: #fff;
    color: #111;
    padding: 22px;
    border-radius: 12px;
    width: 100%;
    max-width: 420px;
    box-shadow: 0 15px 30px rgba(0,0,0,0.22);
    animation: cg-zoom .35s ease;
  }

  @keyframes cg-zoom {
    from { transform: scale(.95); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
  }

  .cg-toggle-row {
    display: flex;
    justify-content: space-between;
    margin: 12px 0;
    font-size: .92rem;
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
