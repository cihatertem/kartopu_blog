document.addEventListener("DOMContentLoaded", function () {
    const urlParams = new URLSearchParams(window.location.search);
    const revealFallback = (section, selector) => {
        const fallback = section.querySelector(selector);
        if (fallback) {
            fallback.classList.remove("is-hidden");
        }
    };
    const isChartAvailable = () => typeof Chart !== "undefined";

    if (urlParams.get("popup") === "1" && window.opener) {
        window.opener.location.reload();
        window.close();
        return;
    }

    // -------------------------
    // Textarea character counter
    // -------------------------
    const textarea = document.getElementById("id_body");
    const counter = document.getElementById("char-count");

    if (textarea && counter) {
        const max = Number(textarea.getAttribute("maxlength"));

        function updateCounter() {
            const len = textarea.value.length;
            counter.textContent = len;
            counter.style.color = len >= max ? "red" : "";
        }

        textarea.addEventListener("input", updateCounter);
        updateCounter();
    }

    // -------------------------
    // Social login modal
    // -------------------------
    const loginButton = document.getElementById("social-login-button");
    const modal = document.getElementById("social-login-modal");
    const closeButton = document.getElementById("close-social-login");

    if (loginButton && modal) {
        const openModal = () => {
            modal.classList.add("is-open");
            modal.setAttribute("aria-hidden", "false");
        };

        const closeModal = () => {
            modal.classList.remove("is-open");
            modal.setAttribute("aria-hidden", "true");
        };

        loginButton.addEventListener("click", openModal);

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
                        window.location.reload();
                    }
                }, 500);
            });
        });
    }

    // -------------------------
    // PortfolioSnapshot charts
    // -------------------------
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
                        datasets: [{ data: allocationData.values }],
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: "bottom" },
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
                        datasets: [{ data: allocationData.values }],
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: "bottom" },
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
                        datasets: [{ data: allocationData.values }],
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: "bottom" },
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
});
