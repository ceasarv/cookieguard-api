(function () {
    /**
     * Public function called by embed.js
     * Opens the preferences modal inside the shadow DOM
     */
    window.CookieGuardOpenPrefs = function (cfg, shadow, box, logConsent) {

        // Safety: remove any existing modal to avoid duplicates
        const existing = shadow.querySelector(".cg-modal");
        if (existing) existing.remove();

        // Modal wrapper
        const modal = document.createElement("div");
        modal.className = "cg-modal";

        modal.innerHTML = `
            <div class="cg-modal-content">
                <h3 class="cg-modal-title">Cookie Preferences</h3>

                <div class="cg-option">
                    <label>Necessary</label>
                    <input type="checkbox" checked disabled />
                </div>

                <div class="cg-option">
                    <label>Analytics</label>
                    <input id="cg-analytics" type="checkbox" />
                </div>

                <div class="cg-option">
                    <label>Marketing</label>
                    <input id="cg-marketing" type="checkbox" />
                </div>

                <div class="cg-modal-actions">
                    <button class="cg-save">${cfg.prefs_text || "Save Preferences"}</button>
                    <button class="cg-cancel">Cancel</button>
                </div>
            </div>
        `;

        box.appendChild(modal);

        // cancel closes modal only
        modal.querySelector(".cg-cancel").onclick = () => modal.remove();

        // save logs + closes banner
        modal.querySelector(".cg-save").onclick = () => {
            const prefs = {
                analytics: modal.querySelector("#cg-analytics").checked,
                marketing: modal.querySelector("#cg-marketing").checked,
            };

            localStorage.setItem("cookieguard_prefs", JSON.stringify(prefs));
            logConsent("preferences_saved", prefs);

            modal.remove();

            // Remove the entire banner after saving prefs
            const host = shadow.host;
            if (host) host.remove();
        };
    };
})();
