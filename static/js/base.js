(function () {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("popup") === "1") {
        if (window.opener) {
            window.opener.postMessage("social-auth:complete", "*");
        }
        try {
            localStorage.setItem("social-auth-complete", String(Date.now()));
        } catch (error) {
            console.warn("Unable to write social-auth-complete marker.", error);
        }
        window.setTimeout(() => {
            window.close();
        }, 150);
    }
    const dateTarget = document.getElementById("site-date");
    if (dateTarget) {
        const formatter = new Intl.DateTimeFormat("tr-TR", {
            day: "numeric",
            month: "long",
            year: "numeric",
        });
        dateTarget.textContent = formatter.format(new Date());
    }

    const legalDisclaimer = document.getElementById("legal-disclaimer");
    const legalDisclaimerButton = document.getElementById(
        "legal-disclaimer-accept",
    );
    const legalDisclaimerStorageKey = "legal-disclaimer-acknowledged";

    const hideLegalDisclaimer = () => {
        if (!legalDisclaimer) {
            return;
        }
        legalDisclaimer.classList.add("is-hidden");
        document.body.classList.remove("has-legal-disclaimer");
        legalDisclaimer.setAttribute("aria-hidden", "true");
    };

    if (legalDisclaimer) {
        let isAcknowledged = false;
        try {
            isAcknowledged =
                localStorage.getItem(legalDisclaimerStorageKey) === "1";
        } catch (error) {
            console.warn("Unable to read legal disclaimer marker.", error);
        }

        if (isAcknowledged) {
            hideLegalDisclaimer();
        } else {
            document.body.classList.add("has-legal-disclaimer");
            legalDisclaimer.removeAttribute("aria-hidden");
        }
    }

    if (legalDisclaimerButton) {
        legalDisclaimerButton.addEventListener("click", () => {
            try {
                localStorage.setItem(legalDisclaimerStorageKey, "1");
            } catch (error) {
                console.warn("Unable to store legal disclaimer marker.", error);
            }
            hideLegalDisclaimer();
        });
    }

    const charCountTargets = document.querySelectorAll(
        "[data-char-counter]",
    );

    const updateCharCounter = (field) => {
        if (!field) {
            return;
        }
        const counterId = field.dataset.charCounter;
        if (!counterId) {
            return;
        }
        const counter = document.getElementById(counterId);
        if (!counter) {
            return;
        }
        const maxLength = Number(field.getAttribute("maxlength"));
        if (!Number.isFinite(maxLength)) {
            return;
        }
        const remaining = Math.max(0, maxLength - field.value.length);
        counter.textContent = String(remaining);
    };

    charCountTargets.forEach((field) => {
        updateCharCounter(field);
        field.addEventListener("input", () => updateCharCounter(field));
    });
})();
