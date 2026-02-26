document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("sim-form");
    const inputs = form.querySelectorAll("input, select");
    const ctx = document.getElementById("balanceChart").getContext("2d");
    const runBtn = document.getElementById("run-btn");
    let chart;
    let lastWType;

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
            if (input.type === "checkbox") {
                input.checked = params.get(input.id) === "true";
            } else {
                input.value = params.get(input.id);
            }
        }
        input.addEventListener("input", () => {
            if (input.id !== "run-btn") {
                updateWithdrawalDisplays();
                // We don't auto-run for random scenario if it's too frequent,
                // but for others it's fine.
                const scenario = document.getElementById("scenario").value;
                if (scenario !== "random") {
                    runSimulation();
                }
            }
        });
    });

    lastWType = document.getElementById("w_type").value;

    runBtn.addEventListener("click", runSimulation);

    // Initial run
    updateWithdrawalDisplays();
    runSimulation();

    function updateWithdrawalDisplays() {
        const pv = parseFloat(document.getElementById("pv").value) || 0;
        const wInput = document.getElementById("w");
        let w = parseFloat(wInput.value) || 0;
        const wType = document.getElementById("w_type").value;
        const wLabel = document.getElementById("w-label");
        const wSuffix = document.getElementById("w-suffix");
        const wDisplay = document.getElementById("withdrawal-display");

        if (wType !== lastWType) {
            if (wType === "amount") {
                wInput.value = 40000;
            } else {
                wInput.value = 4;
            }
            w = parseFloat(wInput.value) || 0;
            lastWType = wType;
        }

        if (wType === "amount") {
            wInput.step = "5000";
            wLabel.textContent = "Yıllık Çekim Tutarı";
            wSuffix.textContent = "₺";
            const rate = pv > 0 ? (w / pv) * 100 : 0;
            wDisplay.textContent = `Çekim oranı: %${rate.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        } else {
            wInput.step = "0.1";
            wLabel.textContent = "Yıllık Çekim Oranı";
            wSuffix.textContent = "%";
            const amount = pv * (w / 100);
            wDisplay.textContent = `Çekim miktarı: ${formatCurrency(amount)}`;
        }
    }

    function boxMuller(mean, std) {
        let u = 0,
            v = 0;
        while (u === 0) u = Math.random();
        while (v === 0) v = Math.random();
        let num = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
        return num * std + mean;
    }

    function runSimulation() {
        const pv = parseFloat(document.getElementById("pv").value) || 0;
        const wType = document.getElementById("w_type").value;
        const wValue = parseFloat(document.getElementById("w").value) || 0;
        let wInitial = wValue;
        if (wType === "rate") {
            wInitial = pv * (wValue / 100);
        }

        const inf =
            (parseFloat(document.getElementById("inf").value) || 0) / 100;
        const avgRet =
            (parseFloat(document.getElementById("avg_ret").value) || 0) / 100;
        const stdDev =
            (parseFloat(document.getElementById("std_dev").value) || 0) / 100;
        const scenario = document.getElementById("scenario").value;
        const period = parseInt(document.getElementById("period").value) || 30;

        // Update URL
        const currentParams = new URLSearchParams();
        inputs.forEach((input) => {
            if (input.id && input.value)
                currentParams.set(input.id, input.value);
        });
        const newUrl =
            window.location.pathname +
            (currentParams.toString() ? "?" + currentParams.toString() : "");
        window.history.replaceState({}, "", newUrl);

        let balances = [pv];
        let labels = ["Başlangıç"];
        let currentBalance = pv;
        let currentW = wInitial;
        let depletionYear = null;
        let cumulativeWithdrawal = 0;

        for (let year = 1; year <= period; year++) {
            let ret = avgRet;
            if (scenario === "bad") {
                if (year === 1) ret = -0.15;
                else if (year === 2) ret = -0.1;
                else if (year === 3) ret = -0.05;
            } else if (scenario === "random") {
                ret = boxMuller(avgRet, stdDev);
            }

            // Withdraw at start of year
            let withdrawalThisYear = currentW;
            if (currentBalance < withdrawalThisYear) {
                withdrawalThisYear = Math.max(0, currentBalance);
            }

            cumulativeWithdrawal += withdrawalThisYear;
            currentBalance = (currentBalance - withdrawalThisYear) * (1 + ret);

            if (currentBalance < 0) currentBalance = 0;

            balances.push(currentBalance);
            labels.push(year + ". Yıl");

            if (
                currentBalance === 0 &&
                depletionYear === null &&
                withdrawalThisYear < currentW
            ) {
                depletionYear = year;
            }
            // Increase withdrawal for next year
            currentW *= 1 + inf;
        }

        updateUI(balances, depletionYear, cumulativeWithdrawal);
        updateChart(labels, balances);
    }

    function updateUI(balances, depletionYear, cumulativeWithdrawal) {
        const finalBalance = balances[balances.length - 1];
        document.getElementById("res-exhaustion-year").textContent =
            depletionYear ? `${depletionYear}. Yıl` : "Tükenmedi";
        document.getElementById("res-cumulative-withdrawal").textContent =
            formatCurrency(cumulativeWithdrawal);
        document.getElementById("res-final-balance").textContent =
            formatCurrency(finalBalance);

        const statusMsg = document.getElementById("sim-status");
        if (depletionYear !== null) {
            statusMsg.textContent = `⚠️ Portföyünüz ${depletionYear}. yılda tükeniyor.`;
            statusMsg.className = "sim-status-msg sim-status-msg--warning";
        } else {
            const initialBalance = balances[0];
            if (finalBalance > initialBalance) {
                statusMsg.textContent = "✅ Portföyünüz büyümesini sürdürüyor.";
                statusMsg.className = "sim-status-msg sim-status-msg--success";
            } else {
                statusMsg.textContent =
                    "ℹ️ Portföyünüz azalıyor ancak simülasyon süresince tükenmiyor.";
                statusMsg.className = "sim-status-msg sim-status-msg--warning";
            }
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

    // Listen for theme changes
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
