const assert = require("node:assert/strict");
const test = require("node:test");

const {
    formatDividendCurrency,
    initializeDividendSummaries,
    normalizeDividendSearch,
} = require("../post_detail.js");

const createClassList = (initial = []) => {
    const set = new Set(initial);
    return {
        add(...tokens) {
            tokens.forEach((t) => set.add(t));
        },
        remove(...tokens) {
            tokens.forEach((t) => set.delete(t));
        },
        toggle(token, force) {
            if (force === undefined) {
                if (set.has(token)) {
                    set.delete(token);
                    return false;
                }
                set.add(token);
                return true;
            }
            if (force) {
                set.add(token);
                return true;
            }
            set.delete(token);
            return false;
        },
        contains(token) {
            return set.has(token);
        },
        [Symbol.iterator]() {
            return set[Symbol.iterator]();
        },
    };
};

const createMockElement = ({
    dataset = {},
    classes = [],
    textContent = "",
    value = "",
    children = {},
} = {}) => {
    const attrs = new Map();
    const listeners = new Map();
    const classList = createClassList(classes);
    return {
        dataset: { ...dataset },
        classList,
        textContent,
        value,
        setAttribute(name, val) {
            attrs.set(name, String(val));
        },
        getAttribute(name) {
            return attrs.get(name) ?? null;
        },
        addEventListener(type, handler) {
            const list = listeners.get(type) || [];
            list.push(handler);
            listeners.set(type, list);
        },
        dispatch(type) {
            (listeners.get(type) || []).forEach((fn) => fn());
        },
        querySelector(selector) {
            return children[selector] || null;
        },
    };
};

test("normalizeDividendSearch folds Turkish characters, case, and exchange suffixes", () => {
    const variants = [
        "clebi",
        "CLEBİ",
        "clebı",
        "CLEBı",
        "CLEBI",
        "CLEBI.IS",
        "CLEBİ.IST",
        "clebi.de",
    ];
    variants.forEach((variant) => {
        assert.equal(normalizeDividendSearch(variant), "clebi");
    });

    assert.equal(normalizeDividendSearch("Çimsa Şirketi ĞÜÖ"), "cimsa sirketi guo");
});

test("formatDividendCurrency formats Turkish currency numbers", () => {
    assert.equal(formatDividendCurrency(18468.18, "₺"), "18.468,18 ₺");
    assert.equal(formatDividendCurrency(1000, "₺"), "1.000 ₺");
    assert.equal(formatDividendCurrency(0, "$"), "0 $");
});

test("initializeDividendSummaries filters by selected month and Turkish asset search", () => {
    const createBar = (month, monthName, total, formatted, height, isSelected = false) => {
        const fill = createMockElement({
            classes: ["dividend-summary__bar-fill", `goal-widget__fill--${height}`],
        });
        const tooltip = createMockElement({
            textContent: `${monthName}: ${formatted}`,
        });
        return {
            bar: createMockElement({
                dataset: {
                    month: String(month),
                    monthName,
                    monthTotal: String(total),
                    formattedTotal: formatted,
                    defaultHeight: String(height),
                },
                classes: [
                    "dividend-summary__bar",
                    ...(isSelected ? ["is-selected"] : []),
                    ...(total <= 0 ? ["is-empty"] : []),
                ],
                children: {
                    ".dividend-summary__bar-fill": fill,
                    "[data-dividend-tooltip]": tooltip,
                },
            }),
            fill,
            tooltip,
        };
    };

    const barJan = createBar(1, "Ocak", 0, "0 ₺", 4, false);
    const barApr = createBar(4, "Nisan", 3762.5, "3.762,50 ₺", 75, false);
    const barOct = createBar(10, "Ekim", 5000, "5.000 ₺", 100, true);

    const rowAprClebi = createMockElement({
        dataset: {
            month: "4",
            assetName: "CLEBI",
            assetSearch: "clebi",
            amount: "3762.50",
        },
        classes: ["is-hidden"],
    });
    const rowOctAstor = createMockElement({
        dataset: {
            month: "10",
            assetName: "ASTOR",
            assetSearch: "astor",
            amount: "5000.00",
        },
    });

    const cardAprClebi = createMockElement({
        dataset: {
            month: "4",
            assetName: "CLEBI",
            assetSearch: "clebi",
            amount: "3762.50",
        },
        classes: ["is-hidden"],
    });
    const cardOctAstor = createMockElement({
        dataset: {
            month: "10",
            assetName: "ASTOR",
            assetSearch: "astor",
            amount: "5000.00",
        },
    });

    const searchInput = createMockElement({ value: "" });
    const periodTitle = createMockElement({ textContent: "Ekim Ayı Temettüleri" });
    const tableContainer = createMockElement({ classes: ["dividend-summary__table"] });
    const cardsContainer = createMockElement({ classes: ["dividend-summary__cards"] });
    const emptyMessage = createMockElement({ classes: ["is-hidden"] });

    const section = {
        dataset: {
            dividendSelectedMonth: "10",
            dividendCurrencySymbol: "₺",
        },
        querySelectorAll(selector) {
            if (selector === ".dividend-summary__bar[data-month]") {
                return [barJan.bar, barApr.bar, barOct.bar];
            }
            if (selector === "[data-dividend-row]") {
                return [rowAprClebi, rowOctAstor];
            }
            if (selector === "[data-dividend-card]") {
                return [cardAprClebi, cardOctAstor];
            }
            return [];
        },
        querySelector(selector) {
            const map = {
                "[data-dividend-search]": searchInput,
                "[data-dividend-period-title]": periodTitle,
                ".dividend-summary__table": tableContainer,
                ".dividend-summary__cards": cardsContainer,
                "[data-dividend-empty]": emptyMessage,
            };
            return map[selector] || null;
        },
    };

    const root = {
        querySelectorAll(selector) {
            return selector === ".dividend-summary" ? [section] : [];
        },
    };

    initializeDividendSummaries(root);

    // Default state: Month 10 selected
    assert.equal(barOct.bar.classList.contains("is-selected"), true);
    assert.equal(rowOctAstor.classList.contains("is-hidden"), false);
    assert.equal(rowAprClebi.classList.contains("is-hidden"), true);
    assert.equal(periodTitle.textContent, "Ekim Ayı Temettüleri");

    // Click April bar (month 4)
    barApr.bar.dispatch("click");
    assert.equal(barApr.bar.classList.contains("is-selected"), true);
    assert.equal(barOct.bar.classList.contains("is-selected"), false);
    assert.equal(rowAprClebi.classList.contains("is-hidden"), false);
    assert.equal(rowOctAstor.classList.contains("is-hidden"), true);
    assert.equal(cardAprClebi.classList.contains("is-hidden"), false);
    assert.equal(cardOctAstor.classList.contains("is-hidden"), true);
    assert.equal(periodTitle.textContent, "Nisan Ayı Temettüleri");

    // Search for CLEBİ.IST while on October -> matches April row and highlights April bar
    barOct.bar.dispatch("click");
    searchInput.value = "CLEBİ.IST";
    searchInput.dispatch("input");

    assert.equal(rowAprClebi.classList.contains("is-hidden"), false);
    assert.equal(rowOctAstor.classList.contains("is-hidden"), true);
    assert.equal(barApr.bar.classList.contains("is-search-match"), true);
    assert.equal(barOct.bar.classList.contains("is-search-match"), false);
    assert.equal(barApr.fill.classList.contains("goal-widget__fill--100"), true);
    assert.equal(barOct.fill.classList.contains("goal-widget__fill--4"), true);
    assert.equal(barApr.tooltip.textContent, "Nisan: 3.762,50 ₺");
    assert.equal(periodTitle.textContent, "Arama Sonuçları (CLEBİ.IST)");

    // Search for non-existent stock -> shows empty message
    searchInput.value = "NONEXISTENT";
    searchInput.dispatch("input");
    assert.equal(tableContainer.classList.contains("is-hidden"), true);
    assert.equal(emptyMessage.classList.contains("is-hidden"), false);
    assert.equal(
        emptyMessage.textContent,
        "Aramanızla eşleşen temettü ödemesi bulunamadı.",
    );
});
