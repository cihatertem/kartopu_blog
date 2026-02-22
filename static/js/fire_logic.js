document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("fire-form");
    const inputs = form.querySelectorAll("input");

    // Load from URL
    const params = new URLSearchParams(window.location.search);
    inputs.forEach((input) => {
        // Handle legacy "multiplier" param if it exists
        if (input.id === "withdrawal_rate" && params.has("multiplier")) {
            input.value = (100 / parseFloat(params.get("multiplier"))).toFixed(
                1,
            );
        } else if (params.has(input.id)) {
            input.value = params.get(input.id);
        }

        input.addEventListener("input", calculateFire);
    });

    // Initial calculation
    calculateFire();

    function calculateFire() {
        const pvInput = document.getElementById("pv").value;
        const incomeInput = document.getElementById("income").value;
        const monthlySpendingInput =
            document.getElementById("monthly_spending").value;
        const rInput = document.getElementById("r").value;
        const withdrawalRateInput =
            document.getElementById("withdrawal_rate").value;

        const pv = parseFloat(pvInput) || 0;
        const income = parseFloat(incomeInput) || 0;
        const monthlySpending = parseFloat(monthlySpendingInput) || 0;
        const pmt = income - monthlySpending;
        const r = (parseFloat(rInput) || 0) / 100;
        const spending = monthlySpending * 12;
        const withdrawalRate = parseFloat(withdrawalRateInput) || 4;
        const multiplier = 100 / withdrawalRate;

        // Update URL
        const currentParams = new URLSearchParams();
        if (pvInput) currentParams.set("pv", pvInput);
        if (incomeInput) currentParams.set("income", incomeInput);
        if (monthlySpendingInput)
            currentParams.set("monthly_spending", monthlySpendingInput);
        if (rInput) currentParams.set("r", rInput);
        if (withdrawalRateInput && withdrawalRateInput !== "4")
            currentParams.set("withdrawal_rate", withdrawalRateInput);

        const newUrl =
            window.location.pathname +
            (currentParams.toString() ? "?" + currentParams.toString() : "");
        window.history.replaceState({}, "", newUrl);

        const goal = spending * multiplier;
        let months = 0;
        let statusOverride = null;

        const isInputEmpty = !pvInput && !incomeInput && !monthlySpendingInput;

        if (isInputEmpty) {
            months = Infinity;
            statusOverride = "Hesaplanıyor...";
        } else if (spending <= 0) {
            months = Infinity;
            statusOverride = "Gider girmelisiniz";
        } else if (pv >= goal) {
            months = 0;
            statusOverride = "Zaten Özgürsünüz!";
        } else {
            const monthlyRate = r > 0 ? Math.pow(1 + r, 1 / 12) - 1 : 0;

            if (monthlyRate <= 0) {
                if (pmt <= 0) {
                    months = Infinity;
                    statusOverride = "Asla (Gelir yetersiz)";
                } else {
                    months = (goal - pv) / pmt;
                }
            } else {
                const numerator = goal + pmt / monthlyRate;
                const denominator = pv + pmt / monthlyRate;

                if (denominator <= 0 || numerator <= 0) {
                    months = Infinity;
                    statusOverride = "Asla (Gelir yetersiz)";
                } else {
                    months =
                        Math.log(numerator / denominator) /
                        Math.log(1 + monthlyRate);
                }
            }
        }

        displayResults(months, goal, spending, pmt, income, statusOverride);
    }

    function displayResults(
        months,
        goal,
        annualSpending,
        pmt,
        income,
        statusOverride,
    ) {
        const yearsElement = document.getElementById("res-years");
        const targetElement = document.getElementById("res-target");
        const dateElement = document.getElementById("res-date");
        const annualSpendingElement = document.getElementById(
            "res-annual-spending",
        );
        const savingsElement = document.getElementById("res-savings");
        const savingsRateElement = document.getElementById("res-savings-rate");

        const currencyFormatter = new Intl.NumberFormat("tr-TR", {
            style: "currency",
            currency: "TRY",
            maximumFractionDigits: 0,
        });

        const formatCurrency = (val) =>
            currencyFormatter.format(val).replace("₺", "").trim() + " ₺";

        const savingsRate = income > 0 ? (pmt / income) * 100 : 0;
        savingsElement.textContent = formatCurrency(pmt);
        savingsRateElement.textContent = `%${Math.max(0, savingsRate).toFixed(1)}`;

        annualSpendingElement.textContent = formatCurrency(annualSpending);
        targetElement.textContent = formatCurrency(goal);

        if (statusOverride) {
            yearsElement.textContent = months === Infinity ? "∞" : "0";
            dateElement.textContent = statusOverride;
        } else if (months === Infinity || isNaN(months) || months < 0) {
            yearsElement.textContent = "∞";
            dateElement.textContent = "Asla (Gelir yetersiz)";
        } else {
            const years = (months / 12).toFixed(1);
            yearsElement.textContent = years;

            const targetDate = new Date();
            targetDate.setMonth(targetDate.getMonth() + Math.ceil(months));
            const options = { year: "numeric", month: "long" };
            dateElement.textContent = targetDate.toLocaleDateString(
                "tr-TR",
                options,
            );
        }
    }
});
