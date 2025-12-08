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
                        <div id="categories-container"></div>
                    </div>

                    <!-- TAB: PERSONAL DATA -->
                    <div class="cg-tab-panel hidden" data-panel="personal">
                        <h3>Your personal data</h3>
                        <p>This site may process limited personal data such as anonymized analytics, IP masking, or inferred preferences.</p>
                    </div>

                    <!-- TAB: POLICY -->
                    <div class="cg-tab-panel hidden" data-panel="policy">
                        <h3>Cookie Policy</h3>
                        <p id="cg-policy-text">We use cookies to enhance your browsing experience and analyze our traffic. By clicking 'Accept', you consent to our use of cookies. Read our Cookie Policy to learn more.</p>
                    </div>

                </div>

                <!-- FOOTER BUTTON -->
                <div class="cg-hub-footer">
                    <div class="cg-hub-footer-content">
                        <a href="https://cookieguard.app" target="_blank" rel="noopener" class="cg-prefs-logo" style="display: none;">
                            Powered by <strong>CookieGuard</strong>
                        </a>
                        <button class="cg-save-btn">Save settings</button>
                    </div>
                </div>

            </div>
        `;

        box.appendChild(modal);

        // Show logo if enabled
        if (cfg.show_logo) {
            const logo = modal.querySelector(".cg-prefs-logo");
            if (logo) logo.style.display = "block";
        }

        // Update cookie policy text if provided
        const policyText = modal.querySelector("#cg-policy-text");
        if (cfg.cookie_policy_text && cfg.cookie_policy_text.trim()) {
            policyText.textContent = cfg.cookie_policy_text;
        }

        // Populate categories dynamically
        const categoriesContainer = modal.querySelector("#categories-container");
        const categoryLabels = {
            necessary: 'Strictly Necessary Cookies',
            preferences: 'Preference Cookies',
            analytics: 'Analytical Cookies',
            marketing: 'Marketing Cookies'
        };
        const categoryDescriptions = {
            necessary: 'Essential for the website to function properly. These cannot be disabled.',
            preferences: 'Remember your settings and preferences for a better experience.',
            analytics: 'Help us understand how you use our website to improve it.',
            marketing: 'Used to show you relevant advertisements and track campaign performance.'
        };

        // Always show all 4 categories
        const allCategories = ['necessary', 'preferences', 'analytics', 'marketing'];

        allCategories.forEach(categoryKey => {
            const scripts = cfg.categories && cfg.categories[categoryKey] || [];

            const categoryDiv = document.createElement('div');
            categoryDiv.className = 'cg-category';

            let scriptsHTML = '';
            if (scripts.length > 0) {
                scriptsHTML = scripts.map(script => `
                    <details>
                        <summary>${script.name}</summary>
                        <p>${script.description || 'No description provided.'}</p>
                    </details>
                `).join('');
            }

            const isNecessary = categoryKey === 'necessary';

            categoryDiv.innerHTML = `
                <div class="cg-cat-row">
                    <div>
                        <h3>${categoryLabels[categoryKey]}</h3>
                        <p>${categoryDescriptions[categoryKey]}</p>
                    </div>
                    <label class="cg-switch">
                        <input id="cg-${categoryKey}" type="checkbox" ${isNecessary ? 'checked disabled' : ''}>
                        <span class="cg-slider"></span>
                    </label>
                </div>
                ${scriptsHTML}
            `;

            categoriesContainer.appendChild(categoryDiv);
        });

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
                necessary: true, // Always true
                preferences: modal.querySelector("#cg-preferences")?.checked || false,
                analytics: modal.querySelector("#cg-analytics")?.checked || false,
                marketing: modal.querySelector("#cg-marketing")?.checked || false,
            };

            // Store consent using the blocker
            if (window.CookieGuardBlocker) {
                window.CookieGuardBlocker.setConsent('preferences_saved', prefs);

                // Enable consented categories
                const enabledCategories = ['necessary']; // Always enable necessary
                Object.keys(prefs).forEach(cat => {
                    if (prefs[cat]) enabledCategories.push(cat);
                });
                window.CookieGuardBlocker.enableScripts(enabledCategories);

                // Delete rejected categories
                const rejectedCategories = Object.keys(prefs).filter(cat => !prefs[cat]);
                window.CookieGuardBlocker.deleteCookies(rejectedCategories);
            }

            logConsent("preferences_saved", prefs);

            modal.remove();
            shadow.host.remove();
        };
    };

})();
