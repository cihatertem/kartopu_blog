(function () {
    const themeStorageKey = "theme-preference";

    const prefersDark =
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;

    let storedTheme = null;
    try {
        storedTheme = localStorage.getItem(themeStorageKey);
    } catch (error) {
        storedTheme = null;
    }

    const initialTheme = storedTheme || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", initialTheme);

})();
