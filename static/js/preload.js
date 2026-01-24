(function () {
    const preloadLinks = document.querySelectorAll(
        'link[rel="preload"][as="style"][data-preload-stylesheet="true"]',
    );

    preloadLinks.forEach((link) => {
        const href = link.getAttribute("href");
        if (!href) {
            return;
        }

        const stylesheetLink = document.createElement("link");
        stylesheetLink.rel = "stylesheet";
        stylesheetLink.href = href;
        link.insertAdjacentElement("afterend", stylesheetLink);
    });
})();

