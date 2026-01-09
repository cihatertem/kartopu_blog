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
})();
