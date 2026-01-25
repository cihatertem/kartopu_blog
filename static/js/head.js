(function () {
    const themeStorageKey = "theme-preference";

    let storedTheme = null;
    try {
        storedTheme = localStorage.getItem(themeStorageKey);
    } catch (error) {
        storedTheme = null;
    }

    const initialTheme = storedTheme || "light";
    document.documentElement.setAttribute("data-theme", initialTheme);

})();
