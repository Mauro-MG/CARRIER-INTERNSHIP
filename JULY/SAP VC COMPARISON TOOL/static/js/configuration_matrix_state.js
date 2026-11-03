(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ConfigurationMatrixState = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function orderedSelection(values, validCharacters) {
    const selected = new Set(values && typeof values[Symbol.iterator] === "function" ? values : []);
    return validCharacters.filter((character) => selected.has(character));
  }

  function normalize(matrix, optionCodes, validCharacters) {
    const normalized = {};
    optionCodes.forEach((code) => {
      const values = orderedSelection(matrix && matrix[code], validCharacters);
      if (values.length) normalized[code] = values;
    });
    return normalized;
  }

  function setCodeCharacters(matrix, code, selectedCharacters, validCharacters) {
    const values = orderedSelection(selectedCharacters, validCharacters);
    if (values.length) matrix[code] = values;
    else delete matrix[code];
    return values;
  }

  function selectAll(matrix, code, validCharacters) {
    return setCodeCharacters(matrix, code, validCharacters, validCharacters);
  }

  function clearAll(matrix, code) {
    delete matrix[code];
    return [];
  }

  function visibleCharacters(excludedCharacters, validCharacters) {
    const valid = new Set(validCharacters);
    const excluded = new Set((excludedCharacters || []).filter((character) => valid.has(character)));
    return validCharacters.filter((character) => !excluded.has(character));
  }

  function excludeCharacters(matrix, excludedCharacters, optionCodes, validCharacters) {
    const visible = visibleCharacters(excludedCharacters, validCharacters);
    const excluded = new Set(validCharacters.filter((character) => !visible.includes(character)));
    optionCodes.forEach((code) => {
      setCodeCharacters(
        matrix,
        code,
        (matrix[code] || []).filter((character) => !excluded.has(character)),
        validCharacters
      );
    });
    return visible;
  }

  function selectAllExcept(matrix, code, excludedCharacters, validCharacters) {
    const valid = new Set(validCharacters);
    const excluded = new Set((excludedCharacters || []).filter((character) => valid.has(character)));
    return setCodeCharacters(
      matrix,
      code,
      validCharacters.filter((character) => !excluded.has(character)),
      validCharacters
    );
  }

  function setCell(matrix, code, character, selected, validCharacters) {
    if (!validCharacters.includes(character)) return matrix[code] || [];
    const values = new Set(matrix[code] || []);
    if (selected) values.add(character);
    else values.delete(character);
    return setCodeCharacters(matrix, code, values, validCharacters);
  }

  function view(matrix, optionCodes, validCharacters, orientation) {
    const charactersAsColumns = orientation === "characters_as_columns";
    const rowValues = charactersAsColumns ? optionCodes : validCharacters;
    const columnValues = charactersAsColumns ? validCharacters : optionCodes;
    return {
      rowValues,
      columnValues,
      isSelected(rowValue, columnValue) {
        const code = charactersAsColumns ? rowValue : columnValue;
        const character = charactersAsColumns ? columnValue : rowValue;
        return (matrix[code] || []).includes(character);
      }
    };
  }

  return { normalize, setCodeCharacters, selectAll, clearAll, visibleCharacters, excludeCharacters, selectAllExcept, setCell, view };
});
