from __future__ import annotations

from services.search_token_resolver import CHARACTER_BASED, CODE_BASED, resolve_position_search_tokens


def test_code_based_resolution_uses_matrix_mappings() -> None:
    tokens = resolve_position_search_tokens(
        "30MPW0310G",
        {
            "search_mode": CODE_BASED,
            "configured_positions": [10],
            "positions": {
                "10": {
                    "option_codes": ["1D", "6B"],
                    "allowed_values_by_option_code": {"1D": ["G"], "6B": ["G"]},
                }
            },
        },
    )

    assert [(token.position, token.catalog_character, token.search_token, token.source_mode) for token in tokens] == [
        (10, "G", "1D", CODE_BASED),
        (10, "G", "6B", CODE_BASED),
    ]


def test_character_based_resolution_uses_catalog_character_directly() -> None:
    tokens = resolve_position_search_tokens(
        "30MPW0310G",
        {
            "search_mode": CHARACTER_BASED,
            "structure": [
                {
                    "characteristic_key": "OPTIONS",
                    "start_position": 10,
                    "end_position": 10,
                    "description": "",
                    "used": True,
                }
            ],
            "positions": {
                "10": {
                    "option_codes": ["1D"],
                    "allowed_values_by_option_code": {"1D": ["G"]},
                }
            },
        },
    )

    assert [(token.position, token.catalog_character, token.search_token, token.source_mode) for token in tokens] == [
        (10, "G", "G", CHARACTER_BASED)
    ]


def test_character_based_resolution_preserves_hyphen() -> None:
    tokens = resolve_position_search_tokens(
        "30MPW0310-",
        {
            "search_mode": CHARACTER_BASED,
            "structure": [{"characteristic_key": "OPTIONS", "start_position": 10, "end_position": 10}],
        },
    )

    assert tokens[0].catalog_character == "-"
    assert tokens[0].search_token == "-"


def test_character_based_resolution_prefers_configured_option_positions() -> None:
    tokens = resolve_position_search_tokens(
        "30MPW0310G5",
        {
            "search_mode": CHARACTER_BASED,
            "option_positions": {"start": 11, "end": 11},
            "structure": [{"characteristic_key": "OPTIONS", "start_position": 10, "end_position": 11}],
        },
    )

    assert [(token.position, token.catalog_character, token.search_token) for token in tokens] == [(11, "5", "5")]


def test_code_based_resolution_filters_to_configured_option_positions() -> None:
    tokens = resolve_position_search_tokens(
        "30MPW0310G5",
        {
            "search_mode": CODE_BASED,
            "option_positions": {"start": 11, "end": 11},
            "configured_positions": [10, 11],
            "positions": {
                "10": {"option_codes": ["1D"], "allowed_values_by_option_code": {"1D": ["G"]}},
                "11": {"option_codes": ["6B"], "allowed_values_by_option_code": {"6B": ["5"]}},
            },
        },
    )

    assert [(token.position, token.catalog_character, token.search_token) for token in tokens] == [(11, "5", "6B")]


def test_old_configuration_defaults_to_code_based() -> None:
    tokens = resolve_position_search_tokens(
        "30MPW0310G",
        {
            "configured_positions": [10],
            "positions": {"10": {"option_codes": ["1D"], "allowed_values_by_option_code": {"1D": ["G"]}}},
        },
    )

    assert tokens[0].source_mode == CODE_BASED
    assert tokens[0].search_token == "1D"
