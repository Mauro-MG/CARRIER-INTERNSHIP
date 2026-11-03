"use strict";

const assert = require("assert");
const matrixState = require("../static/js/configuration_matrix_state.js");

const validCharacters = ["-", "0", "1", "2", "3", "A", "B"];
const optionCodes = ["2A", "11", "12"];
const matrix = {
  "2A": ["0", "3"],
  "11": ["1", "3"],
  "12": ["0", "3", "-"]
};

const rowsView = matrixState.view(matrix, optionCodes, validCharacters, "characters_as_rows");
const columnsView = matrixState.view(matrix, optionCodes, validCharacters, "characters_as_columns");
assert.deepStrictEqual(rowsView.rowValues, validCharacters);
assert.deepStrictEqual(columnsView.rowValues, optionCodes);
assert.strictEqual(rowsView.isSelected("3", "12"), true);
assert.strictEqual(columnsView.isSelected("12", "3"), true);

matrixState.setCell(matrix, "11", "-", true, validCharacters);
assert.strictEqual(matrixState.view(matrix, optionCodes, validCharacters, "characters_as_columns").isSelected("11", "-"), true);
assert.strictEqual(matrixState.view(matrix, optionCodes, validCharacters, "characters_as_rows").isSelected("-", "11"), true);

const visibleCharacters = matrixState.excludeCharacters(matrix, ["-", "A", "Z"], optionCodes, validCharacters);
assert.deepStrictEqual(visibleCharacters, ["0", "1", "2", "3", "B"]);
assert.strictEqual(matrix["11"].includes("-"), false);
assert.deepStrictEqual(
  matrixState.view(matrix, optionCodes, visibleCharacters, "characters_as_rows").rowValues,
  visibleCharacters
);
assert.deepStrictEqual(
  matrixState.view(matrix, optionCodes, visibleCharacters, "characters_as_columns").columnValues,
  visibleCharacters
);

assert.deepStrictEqual(matrixState.selectAll(matrix, "12", visibleCharacters), visibleCharacters);
assert.strictEqual(matrix["12"].includes("-"), false);
matrixState.clearAll(matrix, "12");
assert.strictEqual(matrix["12"], undefined);
assert.deepStrictEqual(matrix["2A"], ["0", "3"]);

console.log("configuration_matrix_state: all assertions passed");
