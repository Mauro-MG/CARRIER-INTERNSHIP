(function () {
  const suffixOrder = ["", ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ"];

  function labelForSuffix(group, suffix) {
    return `${group}${suffix}`;
  }

  function updatePosition(position) {
    const toggle = document.querySelector(`[data-position-toggle="${position}"]`);
    const card = document.querySelector(`[data-position-card="${position}"]`);
    const panel = document.querySelector(`[data-position-panel="${position}"]`);
    const status = document.querySelector(`[data-position-status="${position}"]`);
    const summary = document.querySelector(`[data-position-summary="${position}"]`);
    const selected = Boolean(toggle && toggle.checked);

    if (card) card.classList.toggle("selected", selected);
    if (panel) panel.classList.toggle("hidden", !selected);
    if (status) status.textContent = selected ? "Selected" : "Not selected";

    const enabledRanges = Array.from(
      document.querySelectorAll(`[data-range-toggle][data-position="${position}"]:checked`)
    );
    if (summary) {
      summary.textContent = enabledRanges.length
        ? `${enabledRanges.length} option-code group${enabledRanges.length === 1 ? "" : "s"} selected`
        : "No groups selected yet";
    }
  }

  function updateRangePreview(position, group) {
    const enabled = document.querySelector(
      `[data-range-toggle][data-position="${position}"][data-group="${group}"]`
    );
    const start = document.querySelector(
      `[name="range_${position}_${group}_start"]`
    );
    const end = document.querySelector(
      `[name="range_${position}_${group}_end"]`
    );
    const preview = document.querySelector(`[data-range-preview="${position}_${group}"]`);
    if (!enabled || !start || !end || !preview) return;

    if (!enabled.checked) {
      preview.textContent = "Excluded";
      preview.classList.remove("range-error");
      return;
    }

    const startIndex = suffixOrder.indexOf(start.value);
    const endIndex = suffixOrder.indexOf(end.value);
    preview.textContent = `${labelForSuffix(group, start.value)} through ${labelForSuffix(group, end.value)}`;
    preview.classList.toggle("range-error", startIndex > endIndex);
  }

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const positionToggle = target.getAttribute("data-position-toggle");
    if (positionToggle) {
      updatePosition(positionToggle);
      return;
    }

    const position = target.getAttribute("data-position");
    const group = target.getAttribute("data-group");
    if (position && group) {
      updateRangePreview(position, group);
      updatePosition(position);
    }
  });

  document.querySelectorAll("[data-position-toggle]").forEach((toggle) => {
    updatePosition(toggle.getAttribute("data-position-toggle"));
  });

  document.querySelectorAll("[data-range-preview]").forEach((preview) => {
    const [position, group] = preview.getAttribute("data-range-preview").split("_");
    updateRangePreview(position, group);
  });
})();
