(function () {

    window.CookieGuardOpenPrefs = function (cfg, shadow, box, logConsent) {

        // remove any previous modal
        const existing = shadow.querySelector(".cg-modal");
        if (existing) existing.remove();

        const modal = document.createElement("div");
        modal.className = "cg-modal";

        modal.innerHTML = `
            <div class="cg-hub-container">
                
                <!-- HEADER -->
                <div class="cg-hub-header">
                    <h2>About cookies on this site</h2>
                    <button class="cg-close">&times;</button>
                </div>

                <!-- TABS -->
                <div class="cg-hub-tabs">
                    <button class="cg-tab active" data-tab="categories">Categories</button>
                    <button class="cg-tab" data-tab="personal">Personal data</button>
                    <button class="cg-tab" data-tab="policy">Cookie Policy</button>
                </div>

                <!-- CONTENT AREA -->
                <div class="cg-hub-content">

                    <!-- TAB: CATEGORIES -->
                    <div class="cg-tab-panel" data-panel="categories">
                        
                        <!-- CATEGORY: Preferences -->
                        <div class="cg-category">
                            <div class="cg-cat-row">
                                <div>
                                    <h3>Preferences</h3>
                                    <p>Preference cookies enable the website to remember information such as region, theme, or custom settings.</p>
                                </div>
                                <label class="cg-switch">
                                    <input id="cg-prefers" type="checkbox">
                                    <span class="cg-slider"></span>
                                </label>
                            </div>
                            <details>
                                <summary>Intercom</summary>
                                <p>Used for customer chat and preference memory.</p>
                            </details>
                        </div>

                        <!-- CATEGORY: Analytics -->
                        <div class="cg-category">
                            <div class="cg-cat-row">
                                <div>
                                    <h3>Analytical cookies</h3>
                                    <p>Analytical cookies help improve the website by collecting usage data.</p>
                                </div>
                                <label class="cg-switch">
                                    <input id="cg-analytics" type="checkbox">
                                    <span class="cg-slider"></span>
                                </label>
                            </div>

                            <details>
                                <summary>Google Analytics</summary>
                                <p>Collects anonymous visitor statistics.</p>
                            </details>

                            <details>
                                <summary>Hotjar</summary>
                                <p>Heatmaps and session recordings.</p>
                            </details>

                            <details>
                                <summary>Microsoft Clarity</summary>
                                <p>Session replay analytics.</p>
                            </details>

                        </div>

                        <!-- CATEGORY: Marketing -->
                        <div class="cg-category">
                            <div class="cg-cat-row">
                                <div>
                                    <h3>Marketing cookies</h3>
                                    <p>Used for advertising and retargeting.</p>
                                </div>
                                <label class="cg-switch">
                                    <input id="cg-marketing" type="checkbox">
                                    <span class="cg-slider"></span>
                                </label>
                            </div>

                            <details>
                                <summary>Facebook Pixel</summary>
                                <p>Tracks conversions and remarketing.</p>
                            </details>

                            <details>
                                <summary>TikTok Pixel</summary>
                                <p>Remarketing and analytics.</p>
                            </details>

                        </div>

                    </div>

                    <!-- TAB: PERSONAL DATA -->
                    <div class="cg-tab-panel hidden" data-panel="personal">
                        <h3>Your personal data</h3>
                        <p>This site may process limited personal data such as anonymized analytics, IP masking, or inferred preferences.</p>
                    </div>

                    <!-- TAB: POLICY -->
                    <div class="cg-tab-panel hidden" data-panel="policy">
                        <h3>Cookie Policy</h3>
                        <p>Your website owner can link their full cookie policy here.</p>
                    </div>

                </div>

                <!-- FOOTER BUTTON -->
                <div class="cg-hub-footer">
                    <button class="cg-save-btn">Save settings</button>
                </div>

            </div>
        `;

        box.appendChild(modal);

        // tab handlers
        modal.querySelectorAll(".cg-tab").forEach(tab => {
            tab.onclick = () => {
                modal.querySelectorAll(".cg-tab").forEach(t => t.classList.remove("active"));
                modal.querySelectorAll(".cg-tab-panel").forEach(p => p.classList.add("hidden"));
                tab.classList.add("active");
                modal.querySelector(`[data-panel="${tab.dataset.tab}"]`).classList.remove("hidden");
            };
        });

        // close modal button
        modal.querySelector(".cg-close").onclick = () => modal.remove();

        // save handler
        modal.querySelector(".cg-save-btn").onclick = () => {

            const prefs = {
                preferences: modal.querySelector("#cg-prefers").checked,
                analytics: modal.querySelector("#cg-analytics").checked,
                marketing: modal.querySelector("#cg-marketing").checked,
            };

            localStorage.setItem("cookieguard_prefs", JSON.stringify(prefs));

            logConsent("preferences_saved", prefs);

            modal.remove();
            shadow.host.remove();
        };
    };

})();
