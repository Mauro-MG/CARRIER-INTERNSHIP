(function () {
  const data = window.configurationBuilderData;
  const suffixOrder = data.rangeSuffixes;
  const matrixRows = data.matrixRows;
  const optionGroups = data.optionGroups;
  const positions = data.positions;
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
  const matrixApi = window.ConfigurationMatrixState;

  const state = normalizeInitialConfiguration(data.initialConfiguration);
  let activePosition = isCodeBased() ? state.configured_positions[0] || null : null;
  let currentFileName = data.currentFileName || "";
  let dragMode = null;
  let matrixOrientation = "characters_as_rows";

  const els = {
    messages: document.getElementById("builder-messages"),
    productType: document.getElementById("product_type"),
    description: document.getElementById("description"),
    configurationDate: document.getElementById("configuration_date"),
    version: document.getElementById("version"),
    optionPositionsStart: document.getElementById("option_positions_start"),
    optionPositionsEnd: document.getElementById("option_positions_end"),
    structureBody: document.getElementById("structure-body"),
    addStructureRow: document.getElementById("add-structure-row"),
    positionTabs: document.getElementById("position-tabs"),
    editor: document.getElementById("position-editor"),
    empty: document.getElementById("empty-position-message"),
    activeLabel: document.getElementById("active-position-label"),
    activeTitle: document.getElementById("active-position-title"),
    activeSummary: document.getElementById("active-position-summary"),
    rangeBody: document.getElementById("range-editor-body"),
    applicableGroupList: document.getElementById("applicable-group-list"),
    applyApplicableGroups: document.getElementById("apply-applicable-groups"),
    specificGroupNumber: document.getElementById("specific-group-number"),
    addSpecificGroup: document.getElementById("add-specific-group"),
    matrixScroll: document.getElementById("matrix-scroll"),
    matrixColumnCount: document.getElementById("matrix-column-count"),
    matrixSelectionCount: document.getElementById("matrix-selection-count"),
    matrixOrientation: document.getElementById("matrix-orientation"),
    bulkOptionCode: document.getElementById("bulk-option-code"),
    excludeCharacterList: document.getElementById("exclude-character-list"),
    selectAllForCode: document.getElementById("select-all-for-code"),
    clearAllForCode: document.getElementById("clear-all-for-code"),
    applyPositionExclusions: document.getElementById("apply-position-exclusions"),
    characterSave: document.getElementById("character-save-configuration"),
    characterSaveNewVersion: document.getElementById("character-save-new-version"),
    selectedCount: document.getElementById("selected-count"),
    configuredCount: document.getElementById("configured-count"),
    needsCount: document.getElementById("needs-count"),
    cellCount: document.getElementById("cell-count"),
    baseUnitEnabled: document.getElementById("base_unit_enabled"),
    baseUnitSearchType: document.getElementById("base_unit_search_type"),
    baseUnitStart: document.getElementById("base_unit_start_position"),
    baseUnitEnd: document.getElementById("base_unit_end_position"),
    baseUnitTemplate: document.getElementById("base_unit_template"),
    baseUnitSample: document.getElementById("base_unit_sample_catalog"),
    baseUnitPreview: document.getElementById("base_unit_preview"),
    priceColumnEnabled: document.getElementById("price_column_enabled"),
    priceColumnKeyList: document.getElementById("price_column_key_list"),
    priceColumnPreview: document.getElementById("price_column_preview"),
    conditionalPriceEnabled: document.getElementById("conditional_price_enabled"),
    conditionalPricePositions: document.getElementById("conditional_price_positions"),
    save: document.getElementById("save-configuration"),
    saveNewVersion: document.getElementById("save-new-version"),
    selectAll: document.getElementById("select-all-cells"),
    clearAll: document.getElementById("clear-all-cells")
  };

  hydrateProductFields();
  bindEvents();
  renderAll();

  function normalizeInitialConfiguration(initial) {
    if (initial) {
      const loaded = JSON.parse(JSON.stringify(initial));
      loaded.search_mode = normalizeSearchMode(loaded.search_mode);
      loaded.product_type = loaded.product_type || "";
      loaded.description = loaded.description || "";
      loaded.configuration_date = loaded.configuration_date || data.today;
      loaded.version = loaded.version || 1;
      if (!Array.isArray(loaded.structure) || !loaded.structure.length) {
        loaded.structure = JSON.parse(JSON.stringify(data.defaultStructure));
      }
      if (!Array.isArray(loaded.configured_positions)) loaded.configured_positions = [];
      if (!loaded.positions || typeof loaded.positions !== "object") loaded.positions = {};
      loaded.option_positions = normalizeOptionPositions(loaded.option_positions);
      loaded.price_column_criteria = normalizePriceColumnCriteria(loaded.price_column_criteria, loaded.structure);
      loaded.conditional_price_rules = normalizeConditionalPriceRules(loaded.conditional_price_rules);
      return loaded;
    }
    return {
      schema_version: 1,
      product_type: "",
      description: "",
      configuration_date: data.today,
      version: 1,
      created_at: null,
      updated_at: null,
      search_mode: "code_based",
      structure: JSON.parse(JSON.stringify(data.defaultStructure)),
      option_positions: { start: 10, end: 19 },
      base_unit_price_rule: { enabled: false, search_type: "range", start_position: 1, end_position: 9 },
      price_column_criteria: { enabled: false, keys: [] },
      conditional_price_rules: { enabled: false, positions: [] },
      configured_positions: [],
      positions: {}
    };
  }

  function hydrateProductFields() {
    els.productType.value = state.product_type || "";
    els.description.value = state.description || "";
    els.configurationDate.value = state.configuration_date || data.today;
    els.version.value = state.version || "1";
    hydrateOptionPositionFields();
    hydrateBaseUnitFields();
    hydratePriceColumnCriteriaFields();
    hydrateConditionalPriceFields();
  }

  function bindEvents() {
    [els.productType, els.description, els.configurationDate, els.version].forEach((input) => {
      input.addEventListener("input", syncProductFields);
    });
    [els.optionPositionsStart, els.optionPositionsEnd].forEach((input) => {
      if (!input) return;
      input.addEventListener("input", syncOptionPositions);
      input.addEventListener("change", syncOptionPositions);
    });

    [
      els.baseUnitEnabled,
      els.baseUnitSearchType,
      els.baseUnitStart,
      els.baseUnitEnd,
      els.baseUnitTemplate,
      els.baseUnitSample
    ].forEach((input) => {
      if (!input) return;
      input.addEventListener("input", syncBaseUnitRule);
      input.addEventListener("change", syncBaseUnitRule);
    });

    if (els.priceColumnEnabled) {
      els.priceColumnEnabled.addEventListener("change", () => {
        syncPriceColumnCriteria();
        renderPriceColumnCriteria();
      });
    }
    if (els.priceColumnKeyList) {
      els.priceColumnKeyList.addEventListener("change", (event) => {
        if (!event.target.matches("[data-price-column-key]")) return;
        syncPriceColumnCriteria();
        renderPriceColumnPreview();
      });
    }

    [els.conditionalPriceEnabled, els.conditionalPricePositions].forEach((input) => {
      if (!input) return;
      input.addEventListener("input", syncConditionalPriceRules);
      input.addEventListener("change", syncConditionalPriceRules);
    });

    els.addStructureRow.addEventListener("click", () => {
      state.structure.push({
        characteristic_key: "NEW_CHARACTERISTIC",
        start_position: 1,
        end_position: 1,
        description: "",
        used: false,
        specifications: []
      });
      renderStructureRows();
      renderPriceColumnCriteria();
    });

    els.structureBody.addEventListener("input", (event) => {
      const target = event.target;
      if (!target.matches("[data-structure-field]")) return;
      if (target.matches("[data-structure-key]")) {
        target.value = target.value.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "_");
      }
      syncStructureRow(Number(target.dataset.structureIndex));
    });

    els.structureBody.addEventListener("change", (event) => {
      const target = event.target;
      if (!target.matches("[data-structure-field]")) return;
      syncStructureRow(Number(target.dataset.structureIndex));
      if (target.matches("[data-structure-key]")) {
        renderPriceColumnCriteria();
      }
    });

    els.structureBody.addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-structure-row]");
      if (!button) return;
      const index = Number(button.dataset.removeStructureRow);
      const row = state.structure[index];
      const ok = window.confirm(`Remove structure row ${row.characteristic_key || index + 1}?`);
      if (!ok) return;
      state.structure.splice(index, 1);
      renderStructureRows();
      renderPriceColumnCriteria();
    });

    els.structureBody.addEventListener("click", (event) => {
      const button = event.target.closest(
        "[data-add-specification], [data-remove-specification], [data-import-specifications], [data-clear-specifications]"
      );
      if (!button) return;
      if (button.dataset.addSpecification !== undefined) {
        const rowIndex = Number(button.dataset.addSpecification);
        ensureSpecifications(rowIndex).push({
          catalog_value: "",
          label: "",
          description: "",
          allowed: true
        });
        renderStructureRows();
        renderPriceColumnCriteria();
        return;
      }
      if (button.dataset.importSpecifications !== undefined) {
        importSpecifications(Number(button.dataset.importSpecifications));
        return;
      }
      if (button.dataset.clearSpecifications !== undefined) {
        const rowIndex = Number(button.dataset.clearSpecifications);
        const row = state.structure[rowIndex];
        if (!window.confirm(`Clear all specifications for ${row.characteristic_key || rowIndex + 1}?`)) return;
        row.specifications = [];
        renderStructureRows();
        renderPriceColumnCriteria();
        return;
      }
      if (button.dataset.removeSpecification !== undefined) {
        const rowIndex = Number(button.dataset.structureIndex);
        const specIndex = Number(button.dataset.removeSpecification);
        ensureSpecifications(rowIndex).splice(specIndex, 1);
        renderStructureRows();
        renderPriceColumnCriteria();
      }
    });

    els.structureBody.addEventListener("input", (event) => {
      const target = event.target;
      if (!target.matches("[data-specification-field]")) return;
      if (target.matches("[data-specification-value]")) {
        target.value = target.value.trim().toUpperCase().replace(/[^A-Z0-9_-]/g, "");
      }
      syncSpecification(Number(target.dataset.structureIndex), Number(target.dataset.specificationIndex));
    });

    els.structureBody.addEventListener("change", (event) => {
      const target = event.target;
      if (!target.matches("[data-specification-field]")) return;
      syncSpecification(Number(target.dataset.structureIndex), Number(target.dataset.specificationIndex));
    });

    document.querySelectorAll("[data-position-toggle]").forEach((toggle) => {
      toggle.addEventListener("change", () => togglePosition(Number(toggle.dataset.positionToggle), toggle.checked));
    });

    els.positionTabs.addEventListener("click", (event) => {
      const button = event.target.closest("[data-position-tab]");
      if (!button) return;
      activePosition = Number(button.dataset.positionTab);
      renderAll();
    });

    els.rangeBody.addEventListener("change", (event) => {
      if (!event.target.matches("[data-range-field]")) return;
      updateRangesForActivePosition();
    });
    els.applyApplicableGroups.addEventListener("click", applyApplicableGroups);
    els.addSpecificGroup.addEventListener("click", addSpecificGroup);
    els.specificGroupNumber.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      addSpecificGroup();
    });

    els.matrixOrientation.addEventListener("change", () => {
      matrixOrientation = els.matrixOrientation.value;
      renderMatrix(ensurePosition(activePosition));
    });

    els.matrixScroll.addEventListener("mousedown", (event) => {
      const cell = event.target.closest("[data-matrix-cell]");
      if (!cell) return;
      event.preventDefault();
      dragMode = !cell.classList.contains("selected");
      applyCellState(cell, dragMode);
    });

    els.matrixScroll.addEventListener("mouseover", (event) => {
      if (dragMode === null) return;
      const cell = event.target.closest("[data-matrix-cell]");
      if (cell) applyCellState(cell, dragMode);
    });

    els.matrixScroll.addEventListener("keydown", (event) => {
      const cell = event.target.closest("[data-matrix-cell]");
      if (!cell || ![" ", "Enter"].includes(event.key)) return;
      event.preventDefault();
      applyCellState(cell, !cell.classList.contains("selected"));
    });

    els.matrixScroll.addEventListener("click", (event) => {
      const button = event.target.closest("[data-row-action], [data-column-action]");
      if (!button) return;
      if (button.dataset.rowAction) {
        setRow(button.dataset.rowValue, button.dataset.rowAction === "select");
      } else {
        setColumn(button.dataset.optionCode, button.dataset.columnAction === "select");
      }
    });

    document.addEventListener("mouseup", () => {
      dragMode = null;
    });

    els.selectAll.addEventListener("click", () => setAllCells(true));
    els.clearAll.addEventListener("click", () => setAllCells(false));
    els.selectAllForCode.addEventListener("click", () => applyBulkCodeAction("select"));
    els.clearAllForCode.addEventListener("click", () => applyBulkCodeAction("clear"));
    els.applyPositionExclusions.addEventListener("click", applyPositionExclusions);
    els.save.addEventListener("click", () => saveConfiguration({ saveAsNewVersion: false }));
    els.saveNewVersion.addEventListener("click", () => saveConfiguration({ saveAsNewVersion: true }));
    if (els.characterSave) els.characterSave.addEventListener("click", () => saveConfiguration({ saveAsNewVersion: false }));
    if (els.characterSaveNewVersion) els.characterSaveNewVersion.addEventListener("click", () => saveConfiguration({ saveAsNewVersion: true }));
  }

  function syncProductFields() {
    state.product_type = els.productType.value.trim().toUpperCase();
    state.description = els.description.value.trim();
    state.configuration_date = els.configurationDate.value;
    state.version = parseVersion(els.version.value);
  }

  function hydrateOptionPositionFields() {
    state.option_positions = normalizeOptionPositions(state.option_positions);
    if (els.optionPositionsStart) els.optionPositionsStart.value = state.option_positions.start;
    if (els.optionPositionsEnd) els.optionPositionsEnd.value = state.option_positions.end;
  }

  function syncOptionPositions() {
    state.option_positions = {
      start: Number(els.optionPositionsStart ? els.optionPositionsStart.value : 10),
      end: Number(els.optionPositionsEnd ? els.optionPositionsEnd.value : 19)
    };
  }

  function hydrateBaseUnitFields() {
    const rule = normalizeBaseUnitRule(state.base_unit_price_rule);
    state.base_unit_price_rule = rule;
    if (els.baseUnitEnabled) els.baseUnitEnabled.checked = Boolean(rule.enabled);
    if (els.baseUnitSearchType) els.baseUnitSearchType.value = rule.search_type || "range";
    if (els.baseUnitStart) els.baseUnitStart.value = Number(rule.start_position) || 1;
    if (els.baseUnitEnd) els.baseUnitEnd.value = Number(rule.end_position) || 9;
    if (els.baseUnitTemplate) els.baseUnitTemplate.value = rule.template || "";
    updateBaseUnitPreview();
  }

  function syncBaseUnitRule() {
    const searchType = els.baseUnitSearchType ? els.baseUnitSearchType.value : "range";
    state.base_unit_price_rule = {
      enabled: Boolean(els.baseUnitEnabled && els.baseUnitEnabled.checked),
      search_type: searchType,
      start_position: Number(els.baseUnitStart ? els.baseUnitStart.value : 1),
      end_position: Number(els.baseUnitEnd ? els.baseUnitEnd.value : 9),
      template: els.baseUnitTemplate ? els.baseUnitTemplate.value.trim() : ""
    };
    updateBaseUnitPreview();
  }

  function hydratePriceColumnCriteriaFields() {
    state.price_column_criteria = normalizePriceColumnCriteria(state.price_column_criteria, state.structure);
    if (els.priceColumnEnabled) els.priceColumnEnabled.checked = Boolean(state.price_column_criteria.enabled);
    renderPriceColumnCriteria();
  }

  function syncPriceColumnCriteria() {
    const selected = els.priceColumnKeyList
      ? [...els.priceColumnKeyList.querySelectorAll("[data-price-column-key]:checked")].map((input) => input.value)
      : [];
    const available = structureKeys();
    state.price_column_criteria = {
      enabled: Boolean(els.priceColumnEnabled && els.priceColumnEnabled.checked),
      keys: available.filter((key) => selected.includes(key))
    };
  }

  function renderPriceColumnCriteria() {
    if (!els.priceColumnKeyList) return;
    state.price_column_criteria = normalizePriceColumnCriteria(state.price_column_criteria, state.structure);
    if (els.priceColumnEnabled) els.priceColumnEnabled.checked = Boolean(state.price_column_criteria.enabled);

    const keys = structureKeys();
    if (!keys.length) {
      els.priceColumnKeyList.innerHTML = '<p class="criteria-empty">Add Catalog Structure keys before enabling price-column criteria.</p>';
      renderPriceColumnPreview();
      return;
    }
    els.priceColumnKeyList.innerHTML = keys.map((key) => `
      <label class="criteria-choice">
        <input type="checkbox" data-price-column-key value="${escapeHtml(key)}" ${state.price_column_criteria.keys.includes(key) ? "checked" : ""}>
        <span>${escapeHtml(key)}</span>
      </label>
    `).join("");
    renderPriceColumnPreview();
  }

  function renderPriceColumnPreview() {
    if (!els.priceColumnPreview) return;
    const criteria = normalizePriceColumnCriteria(state.price_column_criteria, state.structure);
    if (!criteria.enabled) {
      els.priceColumnPreview.textContent = "Disabled";
      return;
    }
    els.priceColumnPreview.textContent = criteria.keys.length ? criteria.keys.join(" + ") : "Select at least one key";
  }

  function hydrateConditionalPriceFields() {
    const rules = normalizeConditionalPriceRules(state.conditional_price_rules);
    state.conditional_price_rules = rules;
    if (els.conditionalPriceEnabled) els.conditionalPriceEnabled.checked = Boolean(rules.enabled);
    if (els.conditionalPricePositions) els.conditionalPricePositions.value = rules.positions.join(", ");
  }

  function syncConditionalPriceRules() {
    state.conditional_price_rules = {
      enabled: Boolean(els.conditionalPriceEnabled && els.conditionalPriceEnabled.checked),
      positions: parsePositionList(els.conditionalPricePositions ? els.conditionalPricePositions.value : "")
    };
  }

  function togglePosition(position, selected) {
    if (selected) {
      if (!state.configured_positions.includes(position)) state.configured_positions.push(position);
      state.configured_positions.sort((a, b) => a - b);
      ensurePosition(position);
      activePosition = position;
    } else {
      const positionData = state.positions[String(position)];
      if (positionData && countSelectedCells(positionData) > 0) {
        const ok = window.confirm(`Removing position ${position} will delete its matrix selections. Continue?`);
        if (!ok) {
          document.querySelector(`[data-position-toggle="${position}"]`).checked = true;
          return;
        }
      }
      state.configured_positions = state.configured_positions.filter((item) => item !== position);
      delete state.positions[String(position)];
      if (activePosition === position) activePosition = state.configured_positions[0] || null;
    }
    renderAll();
  }

  function ensurePosition(position) {
    const key = String(position);
    if (!state.positions[key]) {
      state.positions[key] = {
        option_code_ranges: [],
        option_codes: [],
        allowed_values_by_option_code: {},
        excluded_characters: [],
        applicable_groups: []
      };
    }
    if (!Array.isArray(state.positions[key].applicable_groups)) {
      state.positions[key].applicable_groups = (state.positions[key].option_code_ranges || [])
        .map((range) => Number(range.group));
    }
    state.positions[key].applicable_groups = normalizeApplicableGroups(state.positions[key].applicable_groups);
    state.positions[key].allowed_values_by_option_code = matrixApi.normalize(
      state.positions[key].allowed_values_by_option_code || {},
      state.positions[key].option_codes || [],
      matrixRows
    );
    state.positions[key].excluded_characters = matrixRows.filter((character) =>
      (state.positions[key].excluded_characters || []).includes(character)
    );
    matrixApi.excludeCharacters(
      state.positions[key].allowed_values_by_option_code,
      state.positions[key].excluded_characters,
      state.positions[key].option_codes || [],
      matrixRows
    );
    return state.positions[key];
  }

  function renderAll() {
    renderModeVisibility();
    renderStructureRows();
    renderPriceColumnCriteria();
    renderPositionCards();
    renderTabs();
    renderEditor();
    updateBaseUnitPreview();
    updateGlobalStats();
  }

  function renderModeVisibility() {
    const codeBased = isCodeBased();
    document.querySelectorAll(".code-mode-only").forEach((element) => element.classList.toggle("hidden", !codeBased));
    document.querySelectorAll(".character-mode-only").forEach((element) => element.classList.toggle("hidden", codeBased));
  }

  function renderStructureRows() {
    els.structureBody.innerHTML = "";
    state.structure.forEach((row, index) => {
      const tr = document.createElement("tr");
      const specCount = Array.isArray(row.specifications) ? row.specifications.length : 0;
      tr.innerHTML = `
        <td><input type="checkbox" data-structure-field data-structure-used data-structure-index="${index}" ${row.used ? "checked" : ""}></td>
        <td><input data-structure-field data-structure-key data-structure-index="${index}" value="${escapeHtml(row.characteristic_key || "")}" placeholder="VOLTAGE"></td>
        <td><input type="number" min="1" step="1" data-structure-field data-structure-start data-structure-index="${index}" value="${Number(row.start_position) || 1}"></td>
        <td><input type="number" min="1" step="1" data-structure-field data-structure-end data-structure-index="${index}" value="${Number(row.end_position) || 1}"></td>
        <td><input data-structure-field data-structure-description data-structure-index="${index}" value="${escapeHtml(row.description || "")}" placeholder="What this part of the catalog number means"></td>
        <td>
          <details class="structure-specifications">
            <summary>${specCount} spec${specCount === 1 ? "" : "s"}</summary>
            <div class="specification-list">
              <div class="bulk-spec-paste">
                <label>
                  <span>Paste specs from Excel</span>
                  <textarea data-specification-paste="${index}" rows="4" placeholder="Catalog Value&#9;Meaning&#9;Notes&#9;Allowed&#10;1&#9;575-3-60&#9;&#9;Y&#10;6&#9;460-3-60"></textarea>
                </label>
                <div class="bulk-spec-actions">
                  <button type="button" class="secondary-button" data-import-specifications="${index}">Paste specs</button>
                  <button type="button" class="secondary-button danger-button" data-clear-specifications="${index}">Clear specs</button>
                </div>
              </div>
              ${renderSpecificationRows(row, index)}
              <button type="button" class="secondary-button" data-add-specification="${index}">Add spec</button>
            </div>
          </details>
          <button type="button" class="secondary-button danger-button remove-structure-row" data-remove-structure-row="${index}">Remove</button>
        </td>
      `;
      els.structureBody.appendChild(tr);
    });
  }

  function syncStructureRow(index) {
    const row = state.structure[index];
    if (!row) return;
    const used = els.structureBody.querySelector(`[data-structure-used][data-structure-index="${index}"]`);
    const key = els.structureBody.querySelector(`[data-structure-key][data-structure-index="${index}"]`);
    const start = els.structureBody.querySelector(`[data-structure-start][data-structure-index="${index}"]`);
    const end = els.structureBody.querySelector(`[data-structure-end][data-structure-index="${index}"]`);
    const description = els.structureBody.querySelector(`[data-structure-description][data-structure-index="${index}"]`);
    row.used = Boolean(used && used.checked);
    row.characteristic_key = key ? key.value.trim().toUpperCase() : "";
    row.start_position = Number(start ? start.value : 1);
    row.end_position = Number(end ? end.value : 1);
    row.description = description ? description.value.trim() : "";
    if (!Array.isArray(row.specifications)) row.specifications = [];
  }

  function renderSpecificationRows(row, rowIndex) {
    const specs = Array.isArray(row.specifications) ? row.specifications : [];
    if (!specs.length) {
      return '<p class="muted specification-empty">No specifications saved for this characteristic.</p>';
    }
    return specs.map((spec, specIndex) => `
      <div class="specification-row">
        <label>
          <span>Allowed</span>
          <input type="checkbox" data-specification-field data-specification-allowed data-structure-index="${rowIndex}" data-specification-index="${specIndex}" ${spec.allowed === false ? "" : "checked"}>
        </label>
        <label>
          <span>Catalog value</span>
          <input data-specification-field data-specification-value data-structure-index="${rowIndex}" data-specification-index="${specIndex}" value="${escapeHtml(spec.catalog_value || "")}" placeholder="1">
        </label>
        <label>
          <span>Meaning</span>
          <input data-specification-field data-specification-label data-structure-index="${rowIndex}" data-specification-index="${specIndex}" value="${escapeHtml(spec.label || "")}" placeholder="575-3-60">
        </label>
        <label>
          <span>Notes</span>
          <input data-specification-field data-specification-description data-structure-index="${rowIndex}" data-specification-index="${specIndex}" value="${escapeHtml(spec.description || "")}" placeholder="Optional notes">
        </label>
        <button type="button" class="secondary-button danger-button" data-structure-index="${rowIndex}" data-remove-specification="${specIndex}">Remove</button>
      </div>
    `).join("");
  }

  function importSpecifications(rowIndex) {
    const textarea = els.structureBody.querySelector(`[data-specification-paste="${rowIndex}"]`);
    const specs = parseSpecificationPaste(textarea ? textarea.value : "");
    if (!specs.length) {
      showMessage("Paste at least one valid specification row.", "error");
      return;
    }

    const existing = ensureSpecifications(rowIndex);
    const byValue = new Map(existing.map((spec, index) => [String(spec.catalog_value || "").toUpperCase(), index]));
    specs.forEach((spec) => {
      const existingIndex = byValue.get(spec.catalog_value);
      if (existingIndex !== undefined) {
        existing[existingIndex] = spec;
      } else {
        byValue.set(spec.catalog_value, existing.length);
        existing.push(spec);
      }
    });
    renderStructureRows();
    const row = state.structure[rowIndex];
    showMessage(`${specs.length} specification row${specs.length === 1 ? "" : "s"} pasted into ${row.characteristic_key}.`, "success");
  }

  function parseSpecificationPaste(text) {
    return String(text)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map(splitSpecificationLine)
      .filter((columns, index) => !isSpecificationHeader(columns, index))
      .map(columnsToSpecification)
      .filter((spec) => spec.catalog_value);
  }

  function splitSpecificationLine(line) {
    if (line.includes("\t")) return line.split("\t");
    if (line.includes("|")) return line.split("|");
    if (line.includes(",")) return line.split(",");
    return line.split(/\s{2,}/);
  }

  function isSpecificationHeader(columns, index) {
    if (index !== 0 || !columns.length) return false;
    const first = String(columns[0]).trim().toUpperCase().replace(/[\s-]+/g, "_");
    return ["CATALOG_VALUE", "VALUE", "DIGIT", "CHARACTER", "CODE"].includes(first);
  }

  function columnsToSpecification(columns) {
    const cleaned = columns.map((column) => String(column || "").trim());
    const allowedText = cleaned[3] || (looksLikeAllowedFlag(cleaned[2]) ? cleaned[2] : "");
    const description = looksLikeAllowedFlag(cleaned[2]) ? "" : cleaned[2] || "";
    const catalogValue = cleaned[0].toUpperCase().replace(/[^A-Z0-9_-]/g, "");
    return {
      catalog_value: catalogValue,
      label: cleaned[1] || catalogValue,
      description,
      allowed: parseAllowedFlag(allowedText)
    };
  }

  function looksLikeAllowedFlag(value) {
    const normalized = String(value || "").trim().toUpperCase();
    return ["Y", "YES", "TRUE", "1", "ALLOWED", "N", "NO", "FALSE", "0", "NOT ALLOWED"].includes(normalized);
  }

  function parseAllowedFlag(value) {
    const normalized = String(value || "").trim().toUpperCase();
    if (["N", "NO", "FALSE", "0", "NOT ALLOWED"].includes(normalized)) return false;
    return true;
  }

  function ensureSpecifications(rowIndex) {
    const row = state.structure[rowIndex];
    if (!Array.isArray(row.specifications)) row.specifications = [];
    return row.specifications;
  }

  function syncSpecification(rowIndex, specIndex) {
    const specs = ensureSpecifications(rowIndex);
    const spec = specs[specIndex];
    if (!spec) return;
    const allowed = els.structureBody.querySelector(`[data-specification-allowed][data-structure-index="${rowIndex}"][data-specification-index="${specIndex}"]`);
    const value = els.structureBody.querySelector(`[data-specification-value][data-structure-index="${rowIndex}"][data-specification-index="${specIndex}"]`);
    const label = els.structureBody.querySelector(`[data-specification-label][data-structure-index="${rowIndex}"][data-specification-index="${specIndex}"]`);
    const description = els.structureBody.querySelector(`[data-specification-description][data-structure-index="${rowIndex}"][data-specification-index="${specIndex}"]`);
    spec.allowed = Boolean(allowed && allowed.checked);
    spec.catalog_value = value ? value.value.trim().toUpperCase() : "";
    spec.label = label ? label.value.trim() : "";
    spec.description = description ? description.value.trim() : "";
  }

  function renderPositionCards() {
    if (!isCodeBased()) return;
    positions.forEach((position) => {
      const selected = state.configured_positions.includes(position);
      const card = document.querySelector(`[data-position-card="${position}"]`);
      const toggle = document.querySelector(`[data-position-toggle="${position}"]`);
      const status = document.querySelector(`[data-position-status="${position}"]`);
      const configured = selected && isPositionConfigured(ensurePosition(position));
      card.classList.toggle("selected", selected);
      toggle.checked = selected;
      status.textContent = selected ? (configured ? "Configured" : "Needs matrix") : "Not selected";
    });
  }

  function renderTabs() {
    if (!isCodeBased()) return;
    els.positionTabs.innerHTML = "";
    state.configured_positions.forEach((position) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `position-tab${position === activePosition ? " active" : ""}`;
      button.dataset.positionTab = String(position);
      button.textContent = `Position ${position}`;
      els.positionTabs.appendChild(button);
    });
  }

  function renderEditor() {
    if (!isCodeBased()) return;
    if (!activePosition) {
      els.editor.classList.add("hidden");
      els.empty.classList.remove("hidden");
      return;
    }

    const positionData = ensurePosition(activePosition);
    els.editor.classList.remove("hidden");
    els.empty.classList.add("hidden");
    els.activeLabel.textContent = `Position ${activePosition}`;
    els.activeTitle.textContent = `Position ${activePosition}`;
    els.activeSummary.textContent = `${positionData.option_codes.length} option-code columns, ${countSelectedCells(positionData)} selected cells.`;
    renderRangeRows(positionData);
    renderMatrix(positionData);
  }

  function renderRangeRows(positionData) {
    els.rangeBody.innerHTML = "";
    const applicableGroups = positionData.applicable_groups || [];
    const displayedGroups = normalizeApplicableGroups([...optionGroups, ...applicableGroups]);
    els.applicableGroupList.innerHTML = displayedGroups.map((group) => `
      <label class="applicable-group-choice">
        <input type="checkbox" value="${group}" ${applicableGroups.includes(group) ? "checked" : ""}>
        <span>${group}${optionGroups.includes(group) ? "" : " (specific)"}</span>
      </label>
    `).join("");
    const rangesByGroup = new Map(positionData.option_code_ranges.map((range) => [Number(range.group), range]));
    applicableGroups.forEach((group) => {
      const range = rangesByGroup.get(group);
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><input type="checkbox" data-range-field data-range-enabled data-group="${group}" ${range ? "checked" : ""}></td>
        <td>Group ${group}</td>
        <td>${renderSuffixSelect(group, "start", range ? suffixFromCode(range.start) : "")}</td>
        <td>${renderSuffixSelect(group, "end", range ? suffixFromCode(range.end) : "Z")}</td>
        <td><span class="range-preview">${range ? `${range.start} through ${range.end}` : "Excluded"}</span></td>
      `;
      els.rangeBody.appendChild(row);
    });
    if (!applicableGroups.length) {
      els.rangeBody.innerHTML = '<tr><td colspan="5" class="matrix-empty">Select the groups that apply to this position above.</td></tr>';
    }
  }

  function renderSuffixSelect(group, field, value) {
    const options = suffixOrder
      .map((suffix) => `<option value="${suffix}" ${suffix === value ? "selected" : ""}>${group}${suffix}</option>`)
      .join("");
    return `<select data-range-field data-group="${group}" data-range-${field}>${options}</select>`;
  }

  function updateRangesForActivePosition() {
    const positionData = ensurePosition(activePosition);
    const previousCodes = new Set(positionData.option_codes);
    const previousSelections = JSON.parse(JSON.stringify(positionData.allowed_values_by_option_code));
    const newRanges = [];
    const newCodes = [];

    (positionData.applicable_groups || []).forEach((group) => {
      const enabled = els.rangeBody.querySelector(`[data-range-enabled][data-group="${group}"]`);
      if (!enabled || !enabled.checked) return;
      const startSuffix = els.rangeBody.querySelector(`[data-range-start][data-group="${group}"]`).value;
      const endSuffix = els.rangeBody.querySelector(`[data-range-end][data-group="${group}"]`).value;
      const start = `${group}${startSuffix}`;
      const end = `${group}${endSuffix}`;
      const generated = generateRange(group, startSuffix, endSuffix);
      if (!generated.length) return;
      newRanges.push({ group, start, end });
      newCodes.push(...generated);
    });

    const sortedCodes = sortOptionCodes([...new Set(newCodes)]);
    const removedCodes = [...previousCodes].filter((code) => !sortedCodes.includes(code) && previousSelections[code]?.length);
    if (removedCodes.length) {
      const ok = window.confirm(
        `Removing this option-code range will delete selections for ${removedCodes.join(", ")}. Continue?`
      );
      if (!ok) {
        renderEditor();
        return;
      }
    }

    positionData.option_code_ranges = newRanges;
    positionData.option_codes = sortedCodes;
    positionData.allowed_values_by_option_code = {};
    sortedCodes.forEach((code) => {
      const values = previousSelections[code] || [];
      if (values.length) positionData.allowed_values_by_option_code[code] = values;
    });
    renderEditor();
    updateGlobalStats();
  }

  function applyApplicableGroups() {
    const positionData = ensurePosition(activePosition);
    const selectedGroups = normalizeApplicableGroups(
      [...els.applicableGroupList.querySelectorAll('input[type="checkbox"]:checked')]
        .map((checkbox) => Number(checkbox.value))
    );
    const removedGroups = (positionData.applicable_groups || []).filter((group) => !selectedGroups.includes(group));
    const removedCodes = positionData.option_codes.filter((code) => removedGroups.includes(optionCodeKey(code)[0]));
    const selectedRemovedCodes = removedCodes.filter((code) => (positionData.allowed_values_by_option_code[code] || []).length);
    if (selectedRemovedCodes.length && !window.confirm(
      `Removing these groups will delete matrix selections for ${selectedRemovedCodes.join(", ")}. Continue?`
    )) {
      renderRangeRows(positionData);
      return;
    }

    positionData.applicable_groups = selectedGroups;
    positionData.option_code_ranges = positionData.option_code_ranges.filter((range) =>
      selectedGroups.includes(Number(range.group))
    );
    const remainingCodes = positionData.option_codes.filter((code) =>
      selectedGroups.includes(optionCodeKey(code)[0])
    );
    positionData.option_codes = remainingCodes;
    removedCodes.forEach((code) => delete positionData.allowed_values_by_option_code[code]);
    renderEditor();
    updateGlobalStats();
    showMessage(
      `Position ${activePosition}: ${selectedGroups.length} applicable group${selectedGroups.length === 1 ? "" : "s"} shown.`,
      "success"
    );
  }

  function addSpecificGroup() {
    const rawValue = els.specificGroupNumber.value.trim();
    if (!/^[1-9][0-9]*$/.test(rawValue)) {
      showMessage("Enter a positive whole-number group.", "error");
      return;
    }
    const group = Number(rawValue);
    if (!Number.isSafeInteger(group)) {
      showMessage("The specific group number is too large.", "error");
      return;
    }
    const positionData = ensurePosition(activePosition);
    if (positionData.applicable_groups.includes(group)) {
      showMessage(`Group ${group} already applies to Position ${activePosition}.`, "error");
      return;
    }
    positionData.applicable_groups = normalizeApplicableGroups([...positionData.applicable_groups, group]);
    els.specificGroupNumber.value = "";
    renderEditor();
    showMessage(`Specific group ${group} added to Position ${activePosition}.`, "success");
  }

  function renderMatrix(positionData) {
    const charactersAsColumns = matrixOrientation === "characters_as_columns";
    const visibleCharacters = getVisibleCharacters(positionData);
    const matrixView = matrixApi.view(positionData.allowed_values_by_option_code, positionData.option_codes, visibleCharacters, matrixOrientation);
    const columnKind = charactersAsColumns ? "character" : "option-code";
    els.matrixColumnCount.textContent = `${matrixView.columnValues.length} ${columnKind} column${matrixView.columnValues.length === 1 ? "" : "s"}`;
    els.matrixSelectionCount.textContent = `${countSelectedCells(positionData)} selected cell${countSelectedCells(positionData) === 1 ? "" : "s"}`;
    renderBulkEditor(positionData);

    if (!positionData.option_codes.length) {
      els.matrixScroll.innerHTML = '<div class="matrix-empty">Select at least one option-code range to generate matrix columns.</div>';
      return;
    }

    const headerCells = matrixView.columnValues.map((columnValue) => `
      <th>
        <span class="matrix-code">${columnValue}</span>
        <span class="column-controls">
          <button type="button" class="mini-button" ${charactersAsColumns ? `data-row-action="select" data-row-value="${columnValue}"` : `data-column-action="select" data-option-code="${columnValue}"`} title="Select ${columnKind} column">+</button>
          <button type="button" class="mini-button" ${charactersAsColumns ? `data-row-action="clear" data-row-value="${columnValue}"` : `data-column-action="clear" data-option-code="${columnValue}"`} title="Clear ${columnKind} column">-</button>
        </span>
      </th>
    `).join("");

    const bodyRows = matrixView.rowValues.map((displayRow) => {
      const cells = matrixView.columnValues.map((displayColumn) => {
        const code = charactersAsColumns ? displayRow : displayColumn;
        const rowValue = charactersAsColumns ? displayColumn : displayRow;
        const selected = matrixView.isSelected(displayRow, displayColumn);
        return `<td class="matrix-cell${selected ? " selected" : ""}" data-matrix-cell data-option-code="${code}" data-row-value="${rowValue}" role="checkbox" aria-checked="${selected}" tabindex="0" title="Position ${activePosition}, option ${code}, character ${rowValue}"></td>`;
      }).join("");
      return `
        <tr>
          <th class="row-header">
            <span class="matrix-code">${displayRow}</span>
            <span class="row-controls">
              <button type="button" class="mini-button" ${charactersAsColumns ? `data-column-action="select" data-option-code="${displayRow}"` : `data-row-action="select" data-row-value="${displayRow}"`} title="Select row">+</button>
              <button type="button" class="mini-button" ${charactersAsColumns ? `data-column-action="clear" data-option-code="${displayRow}"` : `data-row-action="clear" data-row-value="${displayRow}"`} title="Clear row">-</button>
            </span>
          </th>
          ${cells}
        </tr>
      `;
    }).join("");

    els.matrixScroll.innerHTML = `
      <table class="matrix-table">
        <thead><tr><th class="corner">${charactersAsColumns ? "Option Code" : "Character"}</th>${headerCells}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    `;
  }

  function applyCellState(cell, selected) {
    const positionData = ensurePosition(activePosition);
    const code = cell.dataset.optionCode;
    const rowValue = cell.dataset.rowValue;
    matrixApi.setCell(positionData.allowed_values_by_option_code, code, rowValue, selected, getVisibleCharacters(positionData));

    cell.classList.toggle("selected", selected);
    cell.setAttribute("aria-checked", String(selected));
    updateActiveStats();
  }

  function setRow(rowValue, selected) {
    ensurePosition(activePosition).option_codes.forEach((code) => {
      const cell = els.matrixScroll.querySelector(`[data-option-code="${code}"][data-row-value="${rowValue}"]`);
      if (cell) applyCellState(cell, selected);
    });
  }

  function setColumn(code, selected) {
    getVisibleCharacters(ensurePosition(activePosition)).forEach((rowValue) => {
      const cell = els.matrixScroll.querySelector(`[data-option-code="${code}"][data-row-value="${rowValue}"]`);
      if (cell) applyCellState(cell, selected);
    });
  }

  function setAllCells(selected) {
    els.matrixScroll.querySelectorAll("[data-matrix-cell]").forEach((cell) => applyCellState(cell, selected));
  }

  function renderBulkEditor(positionData) {
    const previousCode = els.bulkOptionCode.value;
    els.bulkOptionCode.innerHTML = positionData.option_codes
      .map((code) => `<option value="${code}">${code}</option>`)
      .join("");
    if (positionData.option_codes.includes(previousCode)) els.bulkOptionCode.value = previousCode;
    const excluded = new Set(positionData.excluded_characters || []);
    els.excludeCharacterList.innerHTML = matrixRows.map((character) => `
      <label class="exclude-character">
        <input type="checkbox" value="${character}" ${excluded.has(character) ? "checked" : ""}>
        <span>${character}</span>
      </label>
    `).join("");
    const disabled = !positionData.option_codes.length;
    [els.bulkOptionCode, els.selectAllForCode, els.clearAllForCode].forEach((control) => {
      control.disabled = disabled;
    });
  }

  function applyBulkCodeAction(action) {
    const code = els.bulkOptionCode.value;
    if (!code) return;
    const matrix = ensurePosition(activePosition).allowed_values_by_option_code;
    const visibleCharacters = getVisibleCharacters(ensurePosition(activePosition));
    const selected = action === "select"
      ? matrixApi.selectAll(matrix, code, visibleCharacters)
      : matrixApi.clearAll(matrix, code);
    renderMatrix(ensurePosition(activePosition));
    updateActiveStats();
    showMessage(`${code} assigned to ${selected.length} character${selected.length === 1 ? "" : "s"}.`, "success");
  }

  function applyPositionExclusions() {
    const positionData = ensurePosition(activePosition);
    const excluded = [...els.excludeCharacterList.querySelectorAll('input[type="checkbox"]:checked')]
      .map((input) => input.value);
    positionData.excluded_characters = matrixRows.filter((character) => excluded.includes(character));
    const visible = matrixApi.excludeCharacters(
      positionData.allowed_values_by_option_code,
      excluded,
      positionData.option_codes,
      matrixRows
    );
    renderMatrix(positionData);
    updateActiveStats();
    showMessage(`Position ${activePosition}: ${excluded.length} character${excluded.length === 1 ? "" : "s"} excluded and hidden; ${visible.length} visible.`, "success");
  }

  function getVisibleCharacters(positionData) {
    return matrixApi.visibleCharacters(positionData.excluded_characters || [], matrixRows);
  }

  function updateActiveStats() {
    const positionData = ensurePosition(activePosition);
    const selectedCells = countSelectedCells(positionData);
    els.matrixSelectionCount.textContent = `${selectedCells} selected cell${selectedCells === 1 ? "" : "s"}`;
    els.activeSummary.textContent = `${positionData.option_codes.length} option-code columns, ${selectedCells} selected cells.`;
    updateGlobalStats();
    renderPositionCards();
  }

  function updateGlobalStats() {
    if (!isCodeBased()) return;
    const selectedCount = state.configured_positions.length;
    const configuredCount = state.configured_positions.filter((position) => isPositionConfigured(ensurePosition(position))).length;
    const totalCells = state.configured_positions.reduce((sum, position) => sum + countSelectedCells(ensurePosition(position)), 0);
    els.selectedCount.textContent = String(selectedCount);
    els.configuredCount.textContent = String(configuredCount);
    els.needsCount.textContent = String(selectedCount - configuredCount);
    els.cellCount.textContent = String(totalCells);
  }

  async function saveConfiguration({ saveAsNewVersion, overwrite = false }) {
    syncProductFields();
    syncOptionPositions();
    syncBaseUnitRule();
    syncPriceColumnCriteria();
    syncConditionalPriceRules();
    state.structure.forEach((_, index) => syncStructureRow(index));
    state.structure.forEach((row, rowIndex) => {
      (row.specifications || []).forEach((_, specIndex) => syncSpecification(rowIndex, specIndex));
    });
    clearMessages();
    const response = await fetch("/configurations/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        configuration: state,
        current_file_name: currentFileName,
        overwrite,
        save_as_new_version: saveAsNewVersion
      })
    });
    const result = await response.json();

    if (result.ok) {
      currentFileName = result.file_name;
      showMessage("Configuration saved.", "success");
      window.location.href = result.redirect_url;
      return;
    }

    if (result.conflict) {
      const choice = window.prompt(
        `Configuration ${result.file_name} already exists.\nType O to overwrite, N to create version ${result.suggested_version}, or C to cancel.`,
        "N"
      );
      if (!choice || choice.toUpperCase() === "C") return;
      if (choice.toUpperCase() === "O") return saveConfiguration({ saveAsNewVersion: false, overwrite: true });
      if (choice.toUpperCase() === "N") return saveConfiguration({ saveAsNewVersion: true, overwrite: false });
    }

    (result.errors || ["The configuration could not be saved."]).forEach((error) => showMessage(error, "error"));
  }

  function showMessage(message, category) {
    const alert = document.createElement("div");
    alert.className = `alert ${category}`;
    alert.textContent = message;
    els.messages.appendChild(alert);
  }

  function clearMessages() {
    els.messages.innerHTML = "";
  }

  function isPositionConfigured(positionData) {
    return positionData.option_codes.length > 0 && countSelectedCells(positionData) > 0;
  }

  function countSelectedCells(positionData) {
    return Object.values(positionData.allowed_values_by_option_code || {}).reduce((sum, values) => sum + values.length, 0);
  }

  function suffixFromCode(code) {
    const match = String(code).match(/^[0-9]+([A-Z])?$/);
    return match && match[1] ? match[1] : "";
  }

  function generateRange(group, startSuffix, endSuffix) {
    const startIndex = suffixOrder.indexOf(startSuffix);
    const endIndex = suffixOrder.indexOf(endSuffix);
    if (startIndex === -1 || endIndex === -1 || startIndex > endIndex) return [];
    return suffixOrder.slice(startIndex, endIndex + 1).map((suffix) => `${group}${suffix}`);
  }

  function sortOptionCodes(codes) {
    return codes.sort((left, right) => {
      const leftKey = optionCodeKey(left);
      const rightKey = optionCodeKey(right);
      return leftKey[0] - rightKey[0] || leftKey[1] - rightKey[1];
    });
  }

  function optionCodeKey(code) {
    const match = String(code).match(/^([0-9]+)([A-Z])?$/);
    if (!match) return [999, 999];
    const suffix = match[2] || "";
    return [Number(match[1]), suffix ? alphabet.indexOf(suffix) + 1 : 0];
  }

  function normalizeApplicableGroups(groups) {
    return [...new Set((groups || [])
      .map((group) => Number(group))
      .filter((group) => Number.isSafeInteger(group) && group > 0))]
      .sort((left, right) => left - right);
  }

  function isCodeBased() {
    return normalizeSearchMode(state.search_mode) === "code_based";
  }

  function normalizeSearchMode(value) {
    return String(value || "code_based").trim().toLowerCase() === "character_based" ? "character_based" : "code_based";
  }

  function normalizeOptionPositions(optionPositions) {
    const source = optionPositions && typeof optionPositions === "object" ? optionPositions : {};
    return {
      start: Number(source.start) || 10,
      end: Number(source.end) || 19
    };
  }

  function normalizeBaseUnitRule(rule) {
    const normalized = rule && typeof rule === "object" ? JSON.parse(JSON.stringify(rule)) : {};
    return {
      enabled: Boolean(normalized.enabled),
      search_type: normalized.search_type === "full_search" ? "full_search" : "range",
      start_position: Number(normalized.start_position) || 1,
      end_position: Number(normalized.end_position) || 9,
      template: normalized.template || ""
    };
  }

  function normalizePriceColumnCriteria(criteria, structure) {
    const source = criteria && typeof criteria === "object" ? criteria : {};
    const available = structureKeys(structure);
    const selected = [];
    (Array.isArray(source.keys) ? source.keys : []).forEach((rawKey) => {
      const key = String(rawKey || "").trim().toUpperCase();
      if (key && available.includes(key) && !selected.includes(key)) {
        selected.push(key);
      }
    });
    return {
      enabled: Boolean(source.enabled),
      keys: available.filter((key) => selected.includes(key))
    };
  }

  function structureKeys(structureOverride) {
    const rows = Array.isArray(structureOverride) ? structureOverride : state.structure;
    const keys = [];
    rows.forEach((row) => {
      const key = String(row.characteristic_key || "").trim().toUpperCase();
      if (key && !keys.includes(key)) keys.push(key);
    });
    return keys;
  }

  function normalizeConditionalPriceRules(rules) {
    const source = rules && typeof rules === "object" ? rules : {};
    return {
      enabled: Boolean(source.enabled),
      positions: normalizePositionArray(source.positions)
    };
  }

  function parsePositionList(value) {
    return normalizePositionArray(String(value || "").split(/[\s,;]+/));
  }

  function normalizePositionArray(rawPositions) {
    const values = Array.isArray(rawPositions)
      ? rawPositions
      : rawPositions && typeof rawPositions === "object"
        ? Object.keys(rawPositions).filter((position) => rawPositions[position])
        : [];
    const seen = new Set();
    values.forEach((rawPosition) => {
      const position = Number(rawPosition);
      if (Number.isInteger(position) && position > 0) seen.add(position);
    });
    return [...seen].sort((left, right) => left - right);
  }

  function updateBaseUnitPreview() {
    if (!els.baseUnitPreview) return;
    const rule = normalizeBaseUnitRule(state.base_unit_price_rule);
    document.querySelectorAll(".base-unit-range-field").forEach((field) => {
      field.classList.toggle("hidden", rule.search_type !== "range");
    });
    document.querySelectorAll(".base-unit-template-field").forEach((field) => {
      field.classList.toggle("hidden", rule.search_type !== "full_search");
    });

    const sample = String(els.baseUnitSample ? els.baseUnitSample.value : "").trim().toUpperCase();
    if (!rule.enabled) {
      els.baseUnitPreview.textContent = "Disabled";
      return;
    }
    if (!sample) {
      els.baseUnitPreview.textContent = "Enter a sample catalog to preview";
      return;
    }

    const resolution = rule.search_type === "full_search" ? resolveTemplatePreview(sample, rule.template) : resolveRangePreview(sample, rule);
    els.baseUnitPreview.textContent = resolution.value || resolution.error || "-";
    els.baseUnitPreview.classList.toggle("range-error", Boolean(resolution.error));
  }

  function resolveRangePreview(sample, rule) {
    const start = Number(rule.start_position);
    const end = Number(rule.end_position);
    if (!start || !end || start < 1 || end < start) return { error: "Invalid range" };
    if (end > sample.length) return { error: `Position ${end} is beyond the sample length (${sample.length})` };
    return { value: sample.slice(start - 1, end) };
  }

  function resolveTemplatePreview(sample, template) {
    const text = String(template || "").trim();
    if (!text) return { error: "Enter a template" };
    if (!/\{\d+(?::\d+)?\}/.test(text)) return { error: "Template needs a placeholder like {1:4}" };
    let output = "";
    let cursor = 0;
    const regex = /\{(\d+)(?::(\d+))?\}/g;
    let match;
    while ((match = regex.exec(text)) !== null) {
      const literal = text.slice(cursor, match.index);
      if (/[{}]/.test(literal)) return { error: "Malformed placeholder" };
      const start = Number(match[1]);
      const end = Number(match[2] || match[1]);
      if (start < 1 || end < start) return { error: "Invalid placeholder range" };
      if (end > sample.length) return { error: `Position ${end} is beyond the sample length (${sample.length})` };
      output += literal + sample.slice(start - 1, end);
      cursor = regex.lastIndex;
    }
    const tail = text.slice(cursor);
    if (/[{}]/.test(tail)) return { error: "Malformed placeholder" };
    return { value: output.toUpperCase() };
  }

  function parseVersion(value) {
    const normalized = String(value).trim();
    if (/^[0-9]+$/.test(normalized)) return Number(normalized);
    return normalized || 1;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
