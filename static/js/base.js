(function () {
    const themeStorageKey = "theme-preference";
    const themeToggle = document.querySelector("[data-theme-toggle]");

    const getStoredTheme = () => {
        try {
            return localStorage.getItem(themeStorageKey);
        } catch (error) {
            console.warn("Unable to read theme preference.", error);
            return null;
        }
    };

    const updateThemeToggle = (theme) => {
        if (!themeToggle) {
            return;
        }
        const isDark = theme === "dark";
        themeToggle.setAttribute("aria-pressed", String(isDark));
        const icon = themeToggle.querySelector(".theme-toggle__icon");
        // const text = themeToggle.querySelector(".theme-toggle__text");
        if (icon) {
            icon.textContent = isDark ? "☀️" : "🌙";
        }
        // if (text) {
        //     text.textContent = isDark ? "Açık mod" : "Koyu mod";
        // }
    };

    const applyTheme = (theme) => {
        document.documentElement.setAttribute("data-theme", theme);
        updateThemeToggle(theme);
    };

    let storedTheme = getStoredTheme();
    let activeTheme = storedTheme || "light";
    applyTheme(activeTheme);

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            activeTheme = activeTheme === "dark" ? "light" : "dark";
            applyTheme(activeTheme);
            storedTheme = activeTheme;
            try {
                localStorage.setItem(themeStorageKey, activeTheme);
            } catch (error) {
                console.warn("Unable to store theme preference.", error);
            }
        });
    }

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

    const charCountTargets = document.querySelectorAll("[data-char-counter]");

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

    const mobileQuery = window.matchMedia("(max-width: 599px)");
    const navbar = document.querySelector(".site-header");

    if (navbar) {
        let lastScrollTop = 0;
        let ticking = false;

        const setTopState = (isAtTop) => {
            navbar.classList.toggle("navbar-at-top", isAtTop);
        };

        const updateNavbar = () => {
            const scrollTop = Math.max(
                window.scrollY || document.documentElement.scrollTop || 0,
                0,
            );
            const isAtTop = scrollTop <= 0;

            setTopState(isAtTop);

            if (!mobileQuery.matches) {
                navbar.classList.remove("navbar-hidden");
                navbar.classList.add("navbar-visible");
                lastScrollTop = scrollTop;
                ticking = false;
                return;
            }

            if (isAtTop || scrollTop < lastScrollTop) {
                navbar.classList.remove("navbar-hidden");
                navbar.classList.add("navbar-visible");
            } else if (scrollTop > lastScrollTop) {
                navbar.classList.remove("navbar-visible");
                navbar.classList.add("navbar-hidden");
            }

            lastScrollTop = scrollTop;
            ticking = false;
        };

        const onScroll = () => {
            if (!ticking) {
                window.requestAnimationFrame(updateNavbar);
                ticking = true;
            }
        };

        const onMediaChange = () => {
            lastScrollTop = Math.max(
                window.scrollY || document.documentElement.scrollTop || 0,
                0,
            );
            window.requestAnimationFrame(updateNavbar);
        };

        navbar.classList.add("navbar-visible");
        setTopState((window.scrollY || document.documentElement.scrollTop || 0) <= 0);

        window.addEventListener("scroll", onScroll, { passive: true });
        mobileQuery.addEventListener("change", onMediaChange);
        onMediaChange();
    }

})();
