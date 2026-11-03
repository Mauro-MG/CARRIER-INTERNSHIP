function flash(button, label) {
  const original = button.textContent;
  button.textContent = label;
  window.setTimeout(() => { button.textContent = original; }, 1300);
}

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    flash(button, "Copied");
  } catch (_error) {
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    helper.remove();
    flash(button, "Copied");
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-copy-id], [data-copy-group]");
  if (!button) return;
  if (button.dataset.copyId) {
    const target = document.getElementById(button.dataset.copyId);
    if (target) copyText(target.textContent, button);
    return;
  }
  const records = [...document.querySelectorAll(`[data-copy-record="${button.dataset.copyGroup}"]`)];
  copyText(records.map((record) => record.textContent).join("\n"), button);
});

if (window.location.search.includes("results")) {
  document.getElementById("results")?.scrollIntoView();
}

const historySearch = document.querySelector("[data-history-search]");
if (historySearch) {
  const rows = [...document.querySelectorAll("[data-history-row]")];
  const noMatch = document.querySelector("[data-history-no-match]");
  historySearch.addEventListener("input", () => {
    const query = historySearch.value.trim().toLowerCase();
    let visibleCount = 0;
    for (const row of rows) {
      const matches = row.dataset.tumbling.includes(query);
      row.hidden = !matches;
      if (matches) visibleCount += 1;
    }
    if (noMatch) noMatch.hidden = visibleCount !== 0;
  });
}
