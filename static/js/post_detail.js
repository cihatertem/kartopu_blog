const worstTreemapRatio = (row, shortSide) => {
    if (!row.length || shortSide <= 0) return Number.POSITIVE_INFINITY;

    const rowArea = row.reduce((sum, item) => sum + item.area, 0);
    const largest = Math.max(...row.map((item) => item.area));
    const smallest = Math.min(...row.map((item) => item.area));
    if (rowArea <= 0 || smallest <= 0) return Number.POSITIVE_INFINITY;

    return Math.max(
        (shortSide * shortSide * largest) / (rowArea * rowArea),
        (rowArea * rowArea) / (shortSide * shortSide * smallest),
    );
};

const layoutTreemapRow = (row, rect, tiles) => {
    const rowArea = row.reduce((sum, item) => sum + item.area, 0);
    if (!row.length || rowArea <= 0 || rect.width <= 0 || rect.height <= 0) return;

    if (rect.width >= rect.height) {
        const columnWidth = Math.min(rect.width, rowArea / rect.height);
        let y = rect.y;
        let remainingHeight = rect.height;
        row.forEach((item, index) => {
            const height =
                index === row.length - 1
                    ? remainingHeight
                    : Math.min(remainingHeight, item.area / columnWidth);
            tiles.push({ item, x: rect.x, y, width: columnWidth, height });
            y += height;
            remainingHeight = Math.max(0, remainingHeight - height);
        });
        rect.x += columnWidth;
        rect.width = Math.max(0, rect.width - columnWidth);
    } else {
        const rowHeight = Math.min(rect.height, rowArea / rect.width);
        let x = rect.x;
        let remainingWidth = rect.width;
        row.forEach((item, index) => {
            const width =
                index === row.length - 1
                    ? remainingWidth
                    : Math.min(remainingWidth, item.area / rowHeight);
            tiles.push({ item, x, y: rect.y, width, height: rowHeight });
            x += width;
            remainingWidth = Math.max(0, remainingWidth - width);
        });
        rect.y += rowHeight;
        rect.height = Math.max(0, rect.height - rowHeight);
    }
};

const getSquarifiedTreemap = (items, width, height) => {
    if (!Array.isArray(items) || width <= 0 || height <= 0) return [];

    const positiveItems = items.filter(
        (item) => Number.isFinite(item.amount) && item.amount > 0,
    );
    const total = positiveItems.reduce((sum, item) => sum + item.amount, 0);
    if (!Number.isFinite(total) || total <= 0) return [];

    const remaining = positiveItems.map((item) => ({
        ...item,
        area: (item.amount / total) * width * height,
    }));
    const rect = { x: 0, y: 0, width, height };
    const tiles = [];
    let row = [];

    while (remaining.length && rect.width > 0 && rect.height > 0) {
        const next = remaining[0];
        const shortSide = Math.min(rect.width, rect.height);
        if (
            !row.length ||
            worstTreemapRatio([...row, next], shortSide) <=
                worstTreemapRatio(row, shortSide)
        ) {
            row.push(remaining.shift());
        } else {
            layoutTreemapRow(row, rect, tiles);
            row = [];
        }
    }
    if (row.length) {
        layoutTreemapRow(row, rect, tiles);
    }
    return tiles;
};

if (typeof module !== "undefined" && module.exports) {
    module.exports = {
        getSquarifiedTreemap,
        layoutTreemapRow,
        worstTreemapRatio,
    };
}

const initializePostDetail = () => {
    const urlParams = new URLSearchParams(window.location.search);
    const revealFallback = (section, selector) => {
        const fallback = section.querySelector(selector);
        if (fallback) {
            fallback.classList.remove("is-hidden");
        }
    };
    const isChartAvailable = () => typeof Chart !== "undefined";
    const chartPalette = [
        "#0d6e6e",
        "#e76f51",
        "#e9c46a",
        "#457b9d",
        "#8ab17d",
        "#9b5de5",
        "#f4a261",
        "#264653",
    ];
    const getChartPalette = (length) =>
        Array.from({ length }, (_, index) => chartPalette[index % chartPalette.length]);
    const getDoughnutLegendOptions = () => {
        const legend = { position: "bottom" };
        if (document.documentElement.getAttribute("data-theme") === "dark") {
            legend.labels = { color: "#dde7e9" };
        }
        return legend;
    };

    // -------------------------
    // Textarea character counter
    // -------------------------
    const textareas = document.querySelectorAll('textarea[name="body"]');
    textareas.forEach((textarea) => {
        const form = textarea.closest("form");
        if (!form) return;

        const counter =
            form.querySelector(".char-count") ||
            form.querySelector("#char-count");
        if (!counter) return;

        const max = Number(textarea.getAttribute("maxlength")) || 3000;

        function updateCounter() {
            const len = textarea.value.length;
            counter.textContent = len;
            counter.style.color = len >= max ? "red" : "";
        }

        textarea.addEventListener("input", updateCounter);
        updateCounter();
    });

    // -------------------------
    // Social login modal
    // -------------------------
    const modal = document.getElementById("social-login-modal");
    const closeButton = document.getElementById("close-social-login");

    const loginButtons = document.querySelectorAll(".social-login-trigger");
    let pendingReload = false;

    if (loginButtons.length > 0 && modal) {
        const requestReload = () => {
            if (modal.classList.contains("is-open")) {
                pendingReload = true;
                return;
            }
            window.location.reload();
        };

        const openModal = () => {
            modal.classList.add("is-open");
            modal.setAttribute("aria-hidden", "false");
        };

        const closeModal = () => {
            modal.classList.remove("is-open");
            modal.setAttribute("aria-hidden", "true");
            if (pendingReload) {
                pendingReload = false;
                window.location.reload();
            }
        };

        loginButtons.forEach((button) => {
            button.addEventListener("click", openModal);
        });

        if (closeButton) {
            closeButton.addEventListener("click", closeModal);
        }

        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                closeModal();
            }
        });

        document.querySelectorAll(".social-login-link").forEach((link) => {
            link.addEventListener("click", (event) => {
                event.preventDefault();
                const url = link.getAttribute("href");
                if (!url) return;

                const popup = window.open(
                    url,
                    "socialLogin",
                    "width=600,height=700,menubar=no,toolbar=no",
                );

                closeModal();

                if (!popup) {
                    window.location.href = url;
                    return;
                }

                const timer = window.setInterval(() => {
                    if (popup.closed) {
                        window.clearInterval(timer);
                        requestReload();
                    }
                }, 500);
            });
        });

        window.addEventListener("message", (event) => {
            if (event.origin !== window.location.origin) return;
            if (event.data?.type === "social-login-complete") {
                requestReload();
            }
        });
    }

    if (urlParams.get("popup") === "1" && window.opener) {
        window.opener.postMessage(
            { type: "social-login-complete" },
            window.location.origin,
        );
        window.close();
        return;
    }

    // -------------------------
    // Post reaction widget
    // -------------------------
    const reactionSection = document.querySelector(".reaction-widget");
    if (reactionSection) {
        const postId = reactionSection.dataset.postId;
        const reactionUrl = reactionSection.dataset.reactionUrl;
        const canReact = reactionSection.dataset.canReact === "true";
        const buttons = Array.from(
            reactionSection.querySelectorAll(".reaction-card"),
        );
        const note = reactionSection.querySelector(".reaction-widget__note");

        const getCookie = (name) => {
            const cookies = document.cookie ? document.cookie.split(";") : [];
            for (const cookie of cookies) {
                const trimmed = cookie.trim();
                if (trimmed.startsWith(`${name}=`)) {
                    return decodeURIComponent(trimmed.slice(name.length + 1));
                }
            }
            return "";
        };
        const getCsrfToken = () =>
            reactionSection.dataset.csrfToken || getCookie("csrftoken");

        const applySelection = (reactionKey) => {
            buttons.forEach((button) => {
                const isSelected = button.dataset.reaction === reactionKey;
                button.classList.toggle("is-selected", isSelected);
                button.setAttribute(
                    "aria-pressed",
                    isSelected ? "true" : "false",
                );
            });

            if (note && canReact) {
                if (reactionKey) {
                    const activeButton = buttons.find(
                        (button) => button.dataset.reaction === reactionKey,
                    );
                    const label =
                        activeButton?.querySelector(".reaction-card__label")
                            ?.textContent || "bir";
                    note.textContent = `Bu yazıda “${label}” tepkisini bıraktın. İstersen değiştirip geri alabilirsin.`;
                } else {
                    note.textContent = "Tepkini seçebilirsin.";
                }
            }
        };

        const applyCounts = (counts) => {
            buttons.forEach((button) => {
                const countEl = button.querySelector("[data-count]");
                if (countEl) {
                    const countValue = counts?.[button.dataset.reaction] ?? 0;
                    countEl.textContent = String(countValue);
                }
            });
        };

        if (postId && buttons.length > 0) {
            const initialSelected = reactionSection.dataset.selected || "";
            applySelection(initialSelected);

            if (!canReact) {
                buttons.forEach((button) => {
                    button.disabled = true;
                    button.classList.add("is-disabled");
                });
            } else {
                buttons.forEach((button) => {
                    button.addEventListener("click", async () => {
                        if (!reactionUrl) return;
                        const reactionKey = button.dataset.reaction;
                        if (!reactionKey) return;
                        const currentSelected =
                            reactionSection.dataset.selected || "";
                        const nextReaction =
                            currentSelected === reactionKey ? "" : reactionKey;

                        try {
                            const response = await fetch(reactionUrl, {
                                method: "POST",
                                headers: {
                                    "Content-Type":
                                        "application/x-www-form-urlencoded",
                                    "X-CSRFToken": getCsrfToken(),
                                },
                                body: new URLSearchParams({
                                    reaction: nextReaction,
                                }).toString(),
                                credentials: "same-origin",
                            });

                            if (!response.ok) {
                                throw new Error("reaction failed");
                            }

                            const payload = await response.json();
                            reactionSection.dataset.selected =
                                payload.selected || "";
                            applySelection(payload.selected || "");
                            applyCounts(payload.counts || {});
                        } catch (error) {
                            if (note) {
                                note.textContent =
                                    "Tepki kaydedilirken bir hata oluştu. Lütfen tekrar deneyin.";
                            }
                        }
                    });
                });
            }
        }
    }

    // -------------------------
    // PortfolioSnapshot charts
    // -------------------------
    document.querySelectorAll(".purchase-treemap").forEach((section) => {
        const canvas = section.querySelector(".purchase-treemap__canvas");
        const tooltip = section.querySelector(".purchase-treemap__tooltip");
        if (!canvas || !tooltip) return;

        let items;
        try {
            items = JSON.parse(section.dataset.treemapItems || "[]").filter(
                (item) => Number.isFinite(Number(item.amount)) && Number(item.amount) > 0,
            );
        } catch {
            return;
        }
        if (!items.length) return;

        const render = () => {
            const width = canvas.clientWidth;
            const height = canvas.clientHeight;
            if (!width || !height) return;
            canvas.replaceChildren();
            getSquarifiedTreemap(
                items.map((item) => ({ ...item, amount: Number(item.amount) })),
                width,
                height,
            ).forEach(({ item, x, y, width: tileWidth, height: tileHeight }, index) => {
                const tile = document.createElement("button");
                tile.type = "button";
                tile.className = "purchase-treemap__tile";
                tile.style.left = `${x}px`;
                tile.style.top = `${y}px`;
                tile.style.width = `${Math.max(0, tileWidth)}px`;
                tile.style.height = `${Math.max(0, tileHeight)}px`;
                tile.style.backgroundColor = chartPalette[index % chartPalette.length];
                tile.textContent = item.symbol;
                const showTooltip = () => {
                    tooltip.textContent = `${item.symbol}: ${item.formatted_amount}`;
                    tooltip.classList.add("is-visible");
                };
                tile.addEventListener("pointerenter", showTooltip);
                tile.addEventListener("focus", showTooltip);
                tile.addEventListener("click", showTooltip);
                tile.addEventListener("pointerleave", () =>
                    tooltip.classList.remove("is-visible"),
                );
                tile.addEventListener("blur", () =>
                    tooltip.classList.remove("is-visible"),
                );
                canvas.appendChild(tile);
            });
        };
        render();
        new ResizeObserver(render).observe(canvas);
    });

    document.querySelectorAll(".portfolio-charts").forEach((section) => {
        const fallbackSelector = ".portfolio-chart-fallback";
        if (!isChartAvailable()) {
            revealFallback(section, fallbackSelector);
            return;
        }
        const allocationRaw = section.dataset.portfolioAllocation;
        const timeseriesRaw = section.dataset.portfolioTimeseries;
        if (!allocationRaw || !timeseriesRaw) {
            revealFallback(section, fallbackSelector);
            return;
        }

        let allocationData, timeseriesData;
        try {
            allocationData = JSON.parse(allocationRaw);
            timeseriesData = JSON.parse(timeseriesRaw);
        } catch {
            revealFallback(section, fallbackSelector);
            return;
        }

        const allocationCanvas = section.querySelector(
            'canvas[data-chart-kind="portfolio-allocation"]',
        );
        if (allocationData && allocationCanvas) {
            try {
                new Chart(allocationCanvas, {
                    type: "doughnut",
                    data: {
                        labels: allocationData.labels,
                        datasets: [
                            {
                                data: allocationData.values,
                                backgroundColor: getChartPalette(
                                    allocationData.values.length,
                                ),
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: getDoughnutLegendOptions(),
                            tooltip: {
                                callbacks: {
                                    label(ctx) {
                                        const v = ctx.parsed || 0;
                                        return `${ctx.label}: ${v.toFixed(2)}%`;
                                    },
                                },
                            },
                        },
                    },
                });
            } catch {
                revealFallback(section, fallbackSelector);
            }
        }

        const timeseriesCanvas = section.querySelector(
            'canvas[data-chart-kind="portfolio-timeseries"]',
        );
        if (timeseriesData && timeseriesCanvas) {
            try {
                new Chart(timeseriesCanvas, {
                    type: "line",
                    data: {
                        labels: timeseriesData.labels,
                        datasets: [
                            {
                                data: timeseriesData.values,
                                fill: false,
                                tension: 0.25,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: {
                                ticks: {
                                    maxRotation: 0,
                                    autoSkip: true,
                                    maxTicksLimit: 8,
                                },
                            },
                        },
                    },
                });
            } catch {
                revealFallback(section, fallbackSelector);
            }
        }
    });

    // -------------------------
    // Portfolio IRR charts
    // -------------------------
    document.querySelectorAll(".portfolio-irr-charts").forEach((section) => {
        const fallbackSelector = ".portfolio-irr-chart-fallback";
        if (!isChartAvailable()) {
            revealFallback(section, fallbackSelector);
            return;
        }

        const timeseriesRaw = section.dataset.portfolioIrr;
        if (!timeseriesRaw) {
            revealFallback(section, fallbackSelector);
            return;
        }

        let timeseriesData;
        try {
            timeseriesData = JSON.parse(timeseriesRaw);
        } catch {
            revealFallback(section, fallbackSelector);
            return;
        }

        const timeseriesCanvas = section.querySelector(
            'canvas[data-chart-kind="portfolio-irr"]',
        );

        if (timeseriesData && timeseriesCanvas) {
            try {
                new Chart(timeseriesCanvas, {
                    type: "line",
                    data: {
                        labels: timeseriesData.labels,
                        datasets: [
                            {
                                data: timeseriesData.values,
                                fill: false,
                                tension: 0.25,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label(ctx) {
                                        const v =
                                            ctx.parsed?.y ?? ctx.parsed ?? 0;
                                        return `IRR: ${Number(v).toFixed(2)}%`;
                                    },
                                },
                            },
                        },
                        scales: {
                            x: {
                                ticks: {
                                    maxRotation: 0,
                                    autoSkip: true,
                                    maxTicksLimit: 8,
                                },
                            },
                            y: {
                                ticks: {
                                    callback(value) {
                                        return `${Number(value).toFixed(1)}%`;
                                    },
                                },
                            },
                        },
                    },
                });
            } catch {
                revealFallback(section, fallbackSelector);
            }
        }
    });

    document
        .querySelectorAll(".portfolio-category-charts")
        .forEach((section) => {
            const fallbackSelector = ".portfolio-category-chart-fallback";
            if (!isChartAvailable()) {
                revealFallback(section, fallbackSelector);
                return;
            }
            const allocationRaw = section.dataset.portfolioCategoryAllocation;
            if (!allocationRaw) {
                revealFallback(section, fallbackSelector);
                return;
            }

            let allocationData;
            try {
                allocationData = JSON.parse(allocationRaw);
            } catch {
                revealFallback(section, fallbackSelector);
                return;
            }

            const allocationCanvas = section.querySelector(
                'canvas[data-chart-kind="portfolio-category-allocation"]',
            );
            if (allocationData && allocationCanvas) {
                try {
                    new Chart(allocationCanvas, {
                        type: "doughnut",
                        data: {
                            labels: allocationData.labels,
                            datasets: [
                                {
                                    data: allocationData.values,
                                    backgroundColor: getChartPalette(
                                        allocationData.values.length,
                                    ),
                                },
                            ],
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: getDoughnutLegendOptions(),
                                tooltip: {
                                    callbacks: {
                                        label(ctx) {
                                            const v = ctx.parsed || 0;
                                            return `${ctx.label}: ${v.toFixed(2)}%`;
                                        },
                                    },
                                },
                            },
                        },
                    });
                } catch {
                    revealFallback(section, fallbackSelector);
                }
            }
        });

    document
        .querySelectorAll(".portfolio-comparison-charts")
        .forEach((section) => {
            const fallbackSelector = ".portfolio-comparison-chart-fallback";
            if (!isChartAvailable()) {
                revealFallback(section, fallbackSelector);
                return;
            }
            const comparisonRaw = section.dataset.portfolioComparison;
            if (!comparisonRaw) {
                revealFallback(section, fallbackSelector);
                return;
            }

            let comparisonData;
            try {
                comparisonData = JSON.parse(comparisonRaw);
            } catch {
                revealFallback(section, fallbackSelector);
                return;
            }

            const comparisonCanvas = section.querySelector(
                'canvas[data-chart-kind="portfolio-comparison"]',
            );
            if (comparisonData && comparisonCanvas) {
                try {
                    new Chart(comparisonCanvas, {
                        type: "bar",
                        data: {
                            labels: comparisonData.labels,
                            datasets: [
                                {
                                    label: comparisonData.base_label || "Base",
                                    data: comparisonData.base,
                                },
                                {
                                    label:
                                        comparisonData.compare_label ||
                                        "Compare",
                                    data: comparisonData.compare,
                                },
                            ],
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { position: "bottom" } },
                            scales: {
                                x: {
                                    ticks: {
                                        maxRotation: 0,
                                        autoSkip: true,
                                    },
                                },
                                y: { beginAtZero: true },
                            },
                        },
                    });
                } catch {
                    revealFallback(section, fallbackSelector);
                }
            }
        });

    // -------------------------
    // Cashflow charts
    // -------------------------
    document.querySelectorAll(".cashflow-charts").forEach((section) => {
        const fallbackSelector = ".cashflow-chart-fallback";
        if (!isChartAvailable()) {
            revealFallback(section, fallbackSelector);
            return;
        }
        const allocationRaw = section.dataset.cashflowAllocation;
        const timeseriesRaw = section.dataset.cashflowTimeseries;
        if (!allocationRaw || !timeseriesRaw) {
            revealFallback(section, fallbackSelector);
            return;
        }

        let allocationData, timeseriesData;
        try {
            allocationData = JSON.parse(allocationRaw);
            timeseriesData = JSON.parse(timeseriesRaw);
        } catch {
            revealFallback(section, fallbackSelector);
            return;
        }

        const allocationCanvas = section.querySelector(
            'canvas[data-chart-kind="cashflow-allocation"]',
        );
        const timeseriesCanvas = section.querySelector(
            'canvas[data-chart-kind="cashflow-timeseries"]',
        );

        if (allocationData && allocationCanvas) {
            try {
                new Chart(allocationCanvas, {
                    type: "doughnut",
                    data: {
                        labels: allocationData.labels,
                        datasets: [
                            {
                                data: allocationData.values,
                                backgroundColor: getChartPalette(
                                    allocationData.values.length,
                                ),
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: getDoughnutLegendOptions(),
                            tooltip: {
                                callbacks: {
                                    label(ctx) {
                                        const v = ctx.parsed || 0;
                                        return `${ctx.label}: ${v.toFixed(2)}%`;
                                    },
                                },
                            },
                        },
                    },
                });
            } catch {
                revealFallback(section, fallbackSelector);
            }
        }

        if (timeseriesData && timeseriesCanvas) {
            try {
                new Chart(timeseriesCanvas, {
                    type: "line",
                    data: {
                        labels: timeseriesData.labels,
                        datasets: [
                            {
                                data: timeseriesData.values,
                                fill: false,
                                tension: 0.25,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: {
                                ticks: {
                                    maxRotation: 0,
                                    autoSkip: true,
                                    maxTicksLimit: 8,
                                },
                            },
                        },
                    },
                });
            } catch {
                revealFallback(section, fallbackSelector);
            }
        }
    });

    // -------------------------
    // Savings rate charts
    // -------------------------
    document.querySelectorAll(".savings-rate-charts").forEach((section) => {
        const fallbackSelector = ".savings-rate-chart-fallback";
        if (!isChartAvailable()) {
            revealFallback(section, fallbackSelector);
            return;
        }

        const timeseriesRaw = section.dataset.savingsRateTimeseries;
        if (!timeseriesRaw) {
            revealFallback(section, fallbackSelector);
            return;
        }

        let timeseriesData;
        try {
            timeseriesData = JSON.parse(timeseriesRaw);
        } catch {
            revealFallback(section, fallbackSelector);
            return;
        }

        const timeseriesCanvas = section.querySelector(
            'canvas[data-chart-kind="savings-rate-timeseries"]',
        );

        if (timeseriesData && timeseriesCanvas) {
            try {
                new Chart(timeseriesCanvas, {
                    type: "line",
                    data: {
                        labels: timeseriesData.labels,
                        datasets: [
                            {
                                data: timeseriesData.values,
                                fill: false,
                                tension: 0.25,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label(ctx) {
                                        const v =
                                            ctx.parsed?.y ?? ctx.parsed ?? 0;
                                        return `Tasarruf Oranı: ${Number(v).toFixed(2)}%`;
                                    },
                                },
                            },
                        },
                        scales: {
                            x: {
                                ticks: {
                                    maxRotation: 0,
                                    autoSkip: true,
                                    maxTicksLimit: 8,
                                },
                            },
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    callback(value) {
                                        return `${Number(value).toFixed(0)}%`;
                                    },
                                },
                            },
                        },
                    },
                });
            } catch {
                revealFallback(section, fallbackSelector);
            }
        }
    });

    // -------------------------
    // Cashflow comparison charts
    // -------------------------
    document
        .querySelectorAll(".cashflow-comparison-charts")
        .forEach((section) => {
            const fallbackSelector = ".cashflow-comparison-chart-fallback";
            if (!isChartAvailable()) {
                revealFallback(section, fallbackSelector);
                return;
            }
            const comparisonRaw = section.dataset.cashflowComparison;
            if (!comparisonRaw) {
                revealFallback(section, fallbackSelector);
                return;
            }

            let comparisonData;
            try {
                comparisonData = JSON.parse(comparisonRaw);
            } catch {
                revealFallback(section, fallbackSelector);
                return;
            }

            const comparisonCanvas = section.querySelector(
                'canvas[data-chart-kind="cashflow-comparison"]',
            );

            if (comparisonData && comparisonCanvas) {
                try {
                    new Chart(comparisonCanvas, {
                        type: "bar",
                        data: {
                            labels: comparisonData.labels,
                            datasets: [
                                {
                                    label: comparisonData.base_label || "Base",
                                    data: comparisonData.base,
                                },
                                {
                                    label:
                                        comparisonData.compare_label ||
                                        "Compare",
                                    data: comparisonData.compare,
                                },
                            ],
                        },
                        options: {
                            responsive: true,
                            plugins: { legend: { position: "bottom" } },
                            scales: {
                                x: {
                                    ticks: {
                                        maxRotation: 0,
                                        autoSkip: true,
                                    },
                                },
                                y: { beginAtZero: true },
                            },
                        },
                    });
                } catch {
                    revealFallback(section, fallbackSelector);
                }
            }
        });

    // -------------------------
    // Dividend charts
    // -------------------------
    document.querySelectorAll(".dividend-charts").forEach((section) => {
        const fallbackSelector = ".dividend-chart-fallback";
        if (!isChartAvailable()) {
            revealFallback(section, fallbackSelector);
            return;
        }
        const allocationRaw = section.dataset.dividendAllocation;
        if (!allocationRaw) {
            revealFallback(section, fallbackSelector);
            return;
        }

        let allocationData;
        try {
            allocationData = JSON.parse(allocationRaw);
        } catch {
            revealFallback(section, fallbackSelector);
            return;
        }

        const allocationCanvas = section.querySelector(
            'canvas[data-chart-kind="dividend-allocation"]',
        );

        if (allocationData && allocationCanvas) {
            try {
                new Chart(allocationCanvas, {
                    type: "doughnut",
                    data: {
                        labels: allocationData.labels,
                        datasets: [
                            {
                                data: allocationData.values,
                                backgroundColor: getChartPalette(
                                    allocationData.values.length,
                                ),
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: getDoughnutLegendOptions(),
                            tooltip: {
                                callbacks: {
                                    label(ctx) {
                                        const v = ctx.parsed || 0;
                                        return `${ctx.label}: ${v.toFixed(2)}%`;
                                    },
                                },
                            },
                        },
                    },
                });
            } catch {
                revealFallback(section, fallbackSelector);
            }
        }
    });

    // -------------------------
    // Delete comment confirmation
    // -------------------------
    document.querySelectorAll(".btn-delete-comment").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            if (!confirm("Silmek istediğinize emin misiniz?")) {
                e.preventDefault();
            }
        });
    });

    // -------------------------
    // Social auth callbacks
    // -------------------------
    window.addEventListener("message", (event) => {
        if (event.data === "social-auth:complete") {
            window.location.reload();
        }
    });

    window.addEventListener("storage", (event) => {
        if (event.key === "social-auth-complete") {
            window.location.reload();
        }
    });
};

if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", initializePostDetail);
}
