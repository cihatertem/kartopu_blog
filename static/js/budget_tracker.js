/* budget_tracker.js */
document.addEventListener("DOMContentLoaded", () => {
    // State management
    const state = {
        monthKey: "",
        data: {
            income: 0,
            livingCosts: [],
            emergencyFund: { targetMonths: 3, currentAmount: 0 },
            debts: [],
            investments: { bes: 0, stockFund: 0 },
            reserve: 0,
        },
    };

    let chartInstance = null;

    // Elements
    const elements = {
        monthSelector: document.getElementById("bt-month-select"),
        pills: document.querySelectorAll(".step-pill"),
        steps: document.querySelectorAll(".step-content"),
        nextBtns: document.querySelectorAll(".next-step"),
        prevBtns: document.querySelectorAll(".prev-step"),
        addCostBtn: document.getElementById("add-cost-btn"),
        addDebtBtn: document.getElementById("add-debt-btn"),
        livingCostsContainer: document.getElementById("living-costs-container"),
        debtsContainer: document.getElementById("debts-container"),
        copySummaryBtn: document.getElementById("copy-summary-btn"),
        exportCsvBtn: document.getElementById("export-csv-btn"),
    };

    // Initialize
    initMonthSelector();
    loadData();
    setupEventListeners();
    updateUI();

    function initMonthSelector() {
        const now = new Date();
        for (let i = 0; i < 12; i++) {
            const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            const key = `kartopu_budget_${d.getFullYear()}_${(d.getMonth() + 1).toString().padStart(2, "0")}`;
            const label = d.toLocaleDateString("tr-TR", {
                month: "long",
                year: "numeric",
            });

            const option = document.createElement("option");
            option.value = key;
            option.textContent = label;
            elements.monthSelector.appendChild(option);
        }
        state.monthKey = elements.monthSelector.value;
    }

    function saveData() {
        // Collect data from DOM before saving
        state.data.income = parseNumber(
            document.getElementById("monthly-income").value,
        );

        state.data.livingCosts = [];
        document.querySelectorAll(".cost-row").forEach((row) => {
            const name = row.querySelector(".cost-name").value;
            const amount = parseNumber(row.querySelector(".cost-amount").value);
            if (name || amount) state.data.livingCosts.push({ name, amount });
        });

        state.data.emergencyFund.targetMonths =
            parseInt(document.getElementById("ef-target").value) || 3;
        state.data.emergencyFund.currentAmount = parseNumber(
            document.getElementById("ef-current").value,
        );

        state.data.debts = [];
        document.querySelectorAll(".debt-row").forEach((row) => {
            const name = row.querySelector(".debt-name").value;
            const amount = parseNumber(row.querySelector(".debt-amount").value);
            if (name || amount) state.data.debts.push({ name, amount });
        });
        // Sort debts smallest to largest (Snowball method)
        state.data.debts.sort((a, b) => a.amount - b.amount);

        state.data.investments.bes = parseNumber(
            document.getElementById("inv-bes").value,
        );
        state.data.investments.stockFund = parseNumber(
            document.getElementById("inv-stock").value,
        );

        state.data.reserve = parseNumber(
            document.getElementById("reserve-amount").value,
        );

        localStorage.setItem(state.monthKey, JSON.stringify(state.data));
        updateUI();
    }

    function loadData() {
        const saved = localStorage.getItem(state.monthKey);
        if (saved) {
            try {
                state.data = JSON.parse(saved);
            } catch (e) {
                console.error("Data parse error", e);
            }
        } else {
            // Defaults
            state.data = {
                income: 0,
                livingCosts: [],
                emergencyFund: { targetMonths: 3, currentAmount: 0 },
                debts: [],
                investments: { bes: 0, stockFund: 0 },
                reserve: 0,
            };
        }
        populateForms();
    }

    function setupEventListeners() {
        elements.monthSelector.addEventListener("change", (e) => {
            state.monthKey = e.target.value;
            loadData();
            updateUI();
        });

        elements.pills.forEach((pill, index) => {
            pill.addEventListener("click", () => goToStep(index + 1));
        });

        elements.nextBtns.forEach((btn) => {
            btn.addEventListener("click", (e) => {
                saveData();
                goToStep(parseInt(e.target.dataset.target));
            });
        });

        elements.prevBtns.forEach((btn) => {
            btn.addEventListener("click", (e) => {
                saveData();
                goToStep(parseInt(e.target.dataset.target));
            });
        });

        elements.addCostBtn.addEventListener("click", () =>
            addRow(elements.livingCostsContainer, "cost"),
        );
        elements.addDebtBtn.addEventListener("click", () =>
            addRow(elements.debtsContainer, "debt"),
        );

        // Attach input events for dynamic calculation
        document.body.addEventListener("input", (e) => {
            if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") {
                // Debounce save
                clearTimeout(window.saveTimeout);
                window.saveTimeout = setTimeout(saveData, 500);
            }
        });

        elements.copySummaryBtn.addEventListener(
            "click",
            copySummaryToClipboard,
        );
        elements.exportCsvBtn.addEventListener("click", exportToCsv);
    }

    function goToStep(stepNum) {
        elements.pills.forEach((p) => p.classList.remove("active"));
        elements.steps.forEach((s) => s.classList.remove("active"));

        document
            .querySelector(`.step-pill[data-step="${stepNum}"]`)
            .classList.add("active");
        document.getElementById(`step-${stepNum}`).classList.add("active");

        if (stepNum === 5) renderSummary();
    }

    function addRow(container, type, name = "", amount = "") {
        const div = document.createElement("div");
        div.className = `dynamic-row ${type}-row`;
        div.innerHTML = `
            <input type="text" class="input-field ${type}-name" placeholder="Gider/Borç Adı" value="${name}">
            <input type="number" class="input-field ${type}-amount" placeholder="Tutar (₺)" value="${amount}">
            <button type="button" class="btn btn-danger remove-row" aria-label="Sil">
                <span class="btn-text-desktop">X</span>
                <span class="btn-text-mobile">Sil</span>
            </button>
        `;
        div.querySelector(".remove-row").addEventListener("click", () => {
            div.remove();
            saveData();
        });
        container.appendChild(div);
    }

    function populateForms() {
        document.getElementById("monthly-income").value =
            state.data.income || "";

        elements.livingCostsContainer.innerHTML = "";
        state.data.livingCosts.forEach((cost) =>
            addRow(
                elements.livingCostsContainer,
                "cost",
                cost.name,
                cost.amount,
            ),
        );
        if (state.data.livingCosts.length === 0)
            addRow(elements.livingCostsContainer, "cost");

        document.getElementById("ef-target").value =
            state.data.emergencyFund.targetMonths;
        document.getElementById("ef-current").value =
            state.data.emergencyFund.currentAmount || "";

        elements.debtsContainer.innerHTML = "";
        state.data.debts.forEach((debt) =>
            addRow(elements.debtsContainer, "debt", debt.name, debt.amount),
        );
        if (state.data.debts.length === 0)
            addRow(elements.debtsContainer, "debt");

        document.getElementById("inv-bes").value =
            state.data.investments.bes || "";
        document.getElementById("inv-stock").value =
            state.data.investments.stockFund || "";

        document.getElementById("reserve-amount").value =
            state.data.reserve || "";
    }

    function updateUI() {
        const income = state.data.income || 0;

        // Step 1: Living Costs Badge
        const totalCosts = state.data.livingCosts.reduce(
            (sum, item) => sum + (item.amount || 0),
            0,
        );
        const costRatio = income > 0 ? (totalCosts / income) * 100 : 0;
        const costBadge = document.getElementById("cost-ratio-badge");

        if (costRatio === 0) {
            costBadge.textContent = "Giriş Bekleniyor";
            costBadge.className = "badge";
        } else if (costRatio < 50) {
            costBadge.textContent = `%${Math.round(costRatio)} - Harika (Yeşil)`;
            costBadge.className = "badge badge-success";
        } else if (costRatio <= 65) {
            costBadge.textContent = `%${Math.round(costRatio)} - Dikkatli (Sarı)`;
            costBadge.className = "badge badge-warning";
        } else {
            costBadge.textContent = `%${Math.round(costRatio)} - Riskli (Kırmızı)`;
            costBadge.className = "badge badge-danger";
        }

        // Step 2: Emergency Fund
        const targetFund = totalCosts * state.data.emergencyFund.targetMonths;
        const currentFund = state.data.emergencyFund.currentAmount || 0;
        const fundRatio =
            targetFund > 0
                ? Math.min(100, (currentFund / targetFund) * 100)
                : 0;
        document.getElementById("ef-progress-text").textContent =
            `Hedef: ${formatMoney(targetFund)} | Mevcut: ${formatMoney(currentFund)} (%${Math.round(fundRatio)})`;
        const fillBar = document.getElementById("ef-progress-bar-fill");
        fillBar.style.width = `${fundRatio}%`;
        if (fundRatio === 100) {
            fillBar.classList.add("is-completed");
        } else {
            fillBar.classList.remove("is-completed");
        }

        // Step 3: Debts
        const totalDebts = state.data.debts.reduce(
            (sum, item) => sum + (item.amount || 0),
            0,
        );
        document.getElementById("debt-ratio-text").textContent =
            income > 0
                ? `Borç/Gelir Oranı: %${Math.round((totalDebts / income) * 100)}`
                : "";

        // Step 4: Investments
        const totalInvestments =
            (state.data.investments.bes || 0) +
            (state.data.investments.stockFund || 0);
        document.getElementById("investment-total-text").textContent =
            `Aylık Toplam Yatırım: ${formatMoney(totalInvestments)}`;
    }

    function renderSummary() {
        const totalCosts = state.data.livingCosts.reduce(
            (sum, i) => sum + i.amount,
            0,
        );
        const totalDebts = state.data.debts.reduce(
            (sum, i) => sum + i.amount,
            0,
        );
        const totalInvestments =
            (state.data.investments.bes || 0) +
            (state.data.investments.stockFund || 0);
        const reserve = state.data.reserve || 0;
        const totalAllocated =
            totalCosts + totalDebts + totalInvestments + reserve;
        const income = state.data.income || 0;
        const remaining = income - totalAllocated;

        document.getElementById("summary-income").textContent =
            formatMoney(income);
        document.getElementById("summary-allocated").textContent =
            formatMoney(totalAllocated);
        const remainingEl = document.getElementById("summary-remaining");
        remainingEl.textContent = formatMoney(remaining);
        remainingEl.className =
            remaining < 0
                ? "text-right font-semibold text-danger"
                : remaining === 0
                  ? "text-right font-semibold text-success"
                  : "text-right font-semibold text-warning";

        // Chart render
        const ctx = document.getElementById("budgetChart").getContext("2d");
        if (chartInstance) chartInstance.destroy();

        if (window.Chart) {
            const computedStyle = getComputedStyle(document.body);
            const colorPrimary = computedStyle
                .getPropertyValue("--color-primary")
                .trim();
            const colorDanger = computedStyle
                .getPropertyValue("--danger-color")
                .trim();
            const colorAccent = computedStyle
                .getPropertyValue("--color-accent")
                .trim();
            const colorWarning = computedStyle
                .getPropertyValue("--warning-color")
                .trim();
            const textColor = computedStyle
                .getPropertyValue("--text-primary")
                .trim();

            chartInstance = new Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: [
                        "Yaşama Maliyeti",
                        "Borç Ödemeleri",
                        "Yatırımlar",
                        "Rezerv",
                    ],
                    datasets: [
                        {
                            data: [
                                totalCosts,
                                totalDebts,
                                totalInvestments,
                                reserve,
                            ],
                            backgroundColor: [
                                colorPrimary,
                                colorDanger,
                                colorAccent,
                                colorWarning,
                            ],
                            borderWidth: 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: { color: textColor },
                        },
                    },
                },
            });
        }
    }

    // Re-render chart when theme changes
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === "data-theme" && chartInstance) {
                renderSummary(); // Recompute colors and redraw
            }
        });
    });
    observer.observe(document.documentElement, { attributes: true });

    function copySummaryToClipboard() {
        const income = state.data.income;
        const totalCosts = state.data.livingCosts.reduce(
            (sum, i) => sum + i.amount,
            0,
        );
        const totalDebts = state.data.debts.reduce(
            (sum, i) => sum + i.amount,
            0,
        );
        const totalInvestments =
            state.data.investments.bes + state.data.investments.stockFund;

        const text = `
Maaş Günü Bütçe Özeti:
----------------------
Aylık Gelir: ${formatMoney(income)}
Yaşama Maliyeti: ${formatMoney(totalCosts)} (%${Math.round((totalCosts / income) * 100 || 0)})
Acil Durum Fonu: ${formatMoney(state.data.emergencyFund.currentAmount)} (Hedef: ${state.data.emergencyFund.targetMonths} ay)
Borç Ödemeleri: ${formatMoney(totalDebts)}
Yatırımlar: ${formatMoney(totalInvestments)} (BES: ${formatMoney(state.data.investments.bes)}, Borsa/Fon: ${formatMoney(state.data.investments.stockFund)})
Rezerv: ${formatMoney(state.data.reserve)}
        `.trim();

        navigator.clipboard.writeText(text).then(() => {
            alert(
                "Özet kopyalandı! Şimdi yapay zekaya (Claude/Gemini) yapıştırıp analiz isteyebilirsiniz.",
            );
        });
    }

    function exportToCsv() {
        const rows = [
            ["Kategori", "Ad", "Tutar"],
            ["Gelir", "Aylık Net Maaş", state.data.income],
        ];

        state.data.livingCosts.forEach((c) =>
            rows.push(["Yaşama Maliyeti", c.name, c.amount]),
        );
        state.data.debts.forEach((c) => rows.push(["Borç", c.name, c.amount]));
        rows.push(["Yatırım", "BES", state.data.investments.bes]);
        rows.push(["Yatırım", "Borsa/Fon", state.data.investments.stockFund]);
        rows.push(["Rezerv", "Esneklik Tamponu", state.data.reserve]);

        const csvContent =
            "data:text/csv;charset=utf-8,\uFEFF" +
            rows.map((e) => e.join(";")).join("\n");

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `butce_ozeti_${state.monthKey}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Helpers
    function parseNumber(val) {
        const num = parseFloat(val);
        return isNaN(num) ? 0 : Math.round(num);
    }

    function formatMoney(amount) {
        return Math.round(amount).toLocaleString("tr-TR") + " ₺";
    }
});
