(function () {
    window.CookieGuardOpenPrefs = function (cfg, shadow, box, logConsent) {

        const existing = shadow.querySelector(".cg-modal");
        if (existing) existing.remove();

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
                    <!-- flipped order -->
                    <button class="cg-cancel">Cancel</button>
                    <button class="cg-save">Save Preferences</button>
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

            const host = shadow.host;
            if (host) host.remove();
        };
    };
})();
