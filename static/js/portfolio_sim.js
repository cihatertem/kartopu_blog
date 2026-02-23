document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("sim-form");
    const inputs = form.querySelectorAll("input");
    const ctx = document.getElementById("balanceChart").getContext("2d");
    let chart;

    const currencyFormatter = new Intl.NumberFormat("tr-TR", {
        style: "currency",
        currency: "TRY",
        maximumFractionDigits: 0,
    });

    const formatCurrency = (val) =>
        currencyFormatter.format(val).replace("₺", "").trim() + " ₺";

    // Load from URL
    const params = new URLSearchParams(window.location.search);
    inputs.forEach((input) => {
        if (params.has(input.id)) {
            input.value = params.get(input.id);
        }
        input.addEventListener("input", runSimulation);
    });

    // Initial simulation
    runSimulation();

    function runSimulation() {
        const pv = parseFloat(document.getElementById("pv").value) || 0;
        const rc = (parseFloat(document.getElementById("rc").value) || 0) / 100;
        const rd = (parseFloat(document.getElementById("rd").value) || 0) / 100;
        const w = parseFloat(document.getElementById("w").value) || 0;
        const period = parseInt(document.getElementById("period").value) || 30;

        // Update calculated displays
        const dividendAmount = pv * rd;
        document.getElementById("dividend-amount-display").textContent =
            `Temettü miktarı: ${formatCurrency(dividendAmount)}`;

        const withdrawalRate = pv > 0 ? (w / pv) * 100 : 0;
        document.getElementById("withdrawal-rate-display").textContent =
            `Çekim oranı: %${withdrawalRate.toLocaleString("tr-TR", { maximumFractionDigits: 2 })}`;

        // Update URL
        const currentParams = new URLSearchParams();
        inputs.forEach((input) => {
            if (input.value) currentParams.set(input.id, input.value);
        });
        const newUrl =
            window.location.pathname +
            (currentParams.toString() ? "?" + currentParams.toString() : "");
        window.history.replaceState({}, "", newUrl);

        let balances = [pv];
        let labels = ["Başlangıç"];
        let currentBalance = pv;
        let depletionYear = null;
        let isGrowing = true;

        for (let year = 1; year <= period; year++) {
            currentBalance = currentBalance * (1 + rc + rd) - w;

            if (currentBalance < 0) {
                currentBalance = 0;
                if (depletionYear === null) depletionYear = year;
            }

            balances.push(currentBalance);
            labels.push(year + ". Yıl");
        }

        // Check sustainability (is it growing in the last year?)
        if (balances[balances.length - 1] < balances[balances.length - 2]) {
            isGrowing = false;
        } else {
            isGrowing = true;
        }

        updateUI(balances, depletionYear, isGrowing);
        updateChart(labels, balances);
    }

    function updateUI(balances, depletionYear, isGrowing) {
        const finalBalance = balances[balances.length - 1];
        const initialBalance = balances[0];
        const totalReturn =
            initialBalance > 0
                ? ((finalBalance - initialBalance) / initialBalance) * 100
                : 0;

        document.getElementById("res-final-balance").textContent =
            formatCurrency(finalBalance);
        document.getElementById("res-total-return").textContent =
            `%${totalReturn.toLocaleString("tr-TR", { maximumFractionDigits: 1 })}`;

        const statusMsg = document.getElementById("sim-status");
        if (depletionYear !== null) {
            statusMsg.textContent = `⚠️ Portföyünüz ${depletionYear}. yılda tükeniyor.`;
            statusMsg.className = "sim-status-msg sim-status-msg--warning";
        } else if (isGrowing) {
            statusMsg.textContent =
                "✅ Portföyünüzün sonsuza kadar yeteceği öngörülüyor.";
            statusMsg.className = "sim-status-msg sim-status-msg--success";
        } else {
            statusMsg.textContent =
                "ℹ️ Portföyünüz azalıyor ancak simülasyon süresince tükenmiyor.";
            statusMsg.className = "sim-status-msg sim-status-msg--warning";
        }
    }

    function updateChart(labels, data) {
        if (chart) {
            chart.destroy();
        }

        const isDarkMode =
            document.documentElement.getAttribute("data-theme") === "dark";
        const gridColor = isDarkMode
            ? "rgba(255, 255, 255, 0.1)"
            : "rgba(0, 0, 0, 0.1)";
        const textColor = isDarkMode ? "#e6edf6" : "#1f2a37";

        // Find depletion index to mark it
        const pointBackgroundColors = data.map((val, i) => {
            if (val === 0 && (i === 0 || data[i - 1] > 0)) return "#ff4d4d";
            return "#2f6da1";
        });
        const pointRadii = data.map((val, i) => {
            if (val === 0 && (i === 0 || data[i - 1] > 0)) return 8;
            return 4;
        });

        chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Portföy Değeri",
                        data: data,
                        borderColor: "#2f6da1",
                        backgroundColor: "rgba(47, 109, 161, 0.1)",
                        pointBackgroundColor: pointBackgroundColors,
                        pointRadius: pointRadii,
                        fill: true,
                        tension: 0.3,
                        pointHoverRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return (
                                    " Bakiye: " +
                                    formatCurrency(context.parsed.y)
                                );
                            },
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: gridColor,
                        },
                        ticks: {
                            color: textColor,
                            callback: function (value) {
                                return formatCurrency(value);
                            },
                        },
                    },
                    x: {
                        grid: {
                            color: gridColor,
                        },
                        ticks: {
                            color: textColor,
                        },
                    },
                },
            },
        });
    }

    // Listen for theme changes to update chart colors
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (
                mutation.type === "attributes" &&
                mutation.attributeName === "data-theme"
            ) {
                runSimulation();
            }
        });
    });
    observer.observe(document.documentElement, { attributes: true });
});
