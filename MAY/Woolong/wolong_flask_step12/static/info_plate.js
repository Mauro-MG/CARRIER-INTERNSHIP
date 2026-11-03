(function () {
    const root = document.getElementById("info-plate-root");
    const form = document.getElementById("model-form");
    const input = document.getElementById("model_number");
    const status = document.getElementById("status");
    let timer = null;
    let lastQuery = "";

    function esc(value) {
        if (value === null || value === undefined || value === "") return "—";
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function showStatus(message, type) {
        if (!message) {
            status.className = "status-bar hidden";
            status.textContent = "";
            return;
        }
        status.className = "status-bar " + (type || "info");
        status.textContent = message;
    }

    function rowsTable(rows) {
        if (!rows || rows.length === 0) return '<p class="muted">No values available.</p>';
        return `<table class="kv-table"><tbody>${rows.map(r => `
            <tr><th>${esc(r.label)}</th><td>${esc(r.value)}</td></tr>
        `).join("")}</tbody></table>`;
    }

    function dataTable(table) {
        const rows = table.rows || [];
        const cols = table.columns || [];
        if (!rows.length) return `<section class="plate-section"><h2>${esc(table.title)}</h2><p class="muted">No rows generated.</p></section>`;
        return `<section class="plate-section"><h2>${esc(table.title)}</h2>
            <div class="table-scroll"><table class="data-table">
                <thead><tr>${cols.map(c => `<th>${esc(c.replaceAll("_", " "))}</th>`).join("")}</tr></thead>
                <tbody>${rows.map(row => `<tr>${cols.map(c => `<td>${esc(row[c])}</td>`).join("")}</tr>`).join("")}</tbody>
            </table></div>
        </section>`;
    }

    function renderMessages(messages) {
        if (!messages || !messages.length) return '<p class="ok-text">No errors or warnings.</p>';
        return `<div class="message-list">${messages.map(m => `
            <div class="message ${esc(m.severity || 'info')}">
                <strong>${esc((m.severity || 'info').toUpperCase())}: ${esc(m.code)}</strong>
                <span>${esc(m.message)}</span>
            </div>
        `).join("")}</div>`;
    }

    function renderResult(result) {
        if (!result || !result.info_plate) {
            root.innerHTML = `<section class="empty-state">
                <h2>Ready when you are</h2>
                <p>Type a model number above to generate the full Info_Plate-style visualization.</p>
            </section>`;
            return;
        }
        const plate = result.info_plate;
        const summary = plate.summary_cards || [];
        const sections = plate.sections || [];
        const tables = plate.tables || [];
        const notes = plate.notes || [];
        const complete = plate.complete_field_sections || [];

        root.innerHTML = `
            <section class="nameplate-header">
                <div>
                    <p class="eyebrow">Generated info plate</p>
                    <h1>${esc(plate.model_number || result.model?.model_number || "Model")}</h1>
                </div>
                <span class="pill">Python/Flask calculation</span>
            </section>

            <section class="summary-grid">
                ${summary.map(card => `<article class="summary-card"><span>${esc(card.label)}</span><strong>${esc(card.value)}</strong></article>`).join("")}
            </section>

            <section class="plate-grid">
                ${sections.map(section => `<article class="plate-section"><h2>${esc(section.title)}</h2>${rowsTable(section.rows)}</article>`).join("")}
            </section>

            ${tables.map(dataTable).join("")}

            <section class="plate-section">
                <h2>Notes</h2>
                ${notes.length ? `<ul class="note-list">${notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul>` : '<p class="muted">No notes generated.</p>'}
            </section>

            <section class="plate-section">
                <h2>Errors / warnings</h2>
                ${renderMessages(plate.messages)}
            </section>

            <details class="plate-section details-block">
                <summary>Show every generated field</summary>
                ${complete.map(section => `<h3>${esc(section.title)}</h3>${rowsTable(section.rows)}`).join("")}
            </details>

            <details class="plate-section details-block">
                <summary>Show raw JSON</summary>
                <pre>${esc(JSON.stringify(result, null, 2))}</pre>
            </details>
        `;
    }

    async function calculate(modelNumber, source) {
        const value = (modelNumber || "").trim().toUpperCase();
        if (!value) {
            showStatus("", "info");
            renderResult(null);
            return;
        }
        if (value === lastQuery && source !== "submit") return;
        lastQuery = value;
        showStatus("Calculating info plate…", "info");
        try {
            const response = await fetch("/api/calculate", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({model_number: value})
            });
            if (!response.ok) throw new Error("Calculation request failed");
            const result = await response.json();
            renderResult(result);
            const messages = result.errors?.messages || [];
            const hasError = messages.some(m => m.severity === "error");
            showStatus(hasError ? "Calculated with errors. Review the warning section below." : "Info plate generated.", hasError ? "error" : "success");
        } catch (err) {
            showStatus("Could not calculate the model number. Check the Flask console for details.", "error");
            console.error(err);
        }
    }

    if (form) {
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            calculate(input.value, "submit");
        });
    }

    if (input) {
        input.addEventListener("input", function () {
            clearTimeout(timer);
            const value = input.value.trim();
            if (value.length < 8) {
                showStatus("", "info");
                return;
            }
            timer = setTimeout(() => calculate(value, "typing"), 450);
        });
    }

    renderResult(window.__INITIAL_RESULT__);
})();
