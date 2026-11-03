import json
import hashlib
import ollama
import best_gemma_classifier as bgc

bad_text = """ClaimNumber: CRSASBJ93
ClaimDate: 2024-10-22 00:00:00
ReplacementPartDescription: TXV VALVE, 12.5-TON NOM
ServicePerformed: Unit was confirmed to have issues with 2 txv's."""
bad_part = """TXV VALVE, 12.5-TON NOM"""

def debug_generate(label, text, part, use_json_format=True):
    prompt = bgc.build_prompt(
        text=text,
        replacement_part_description=part
    )

    print("\n" + "=" * 80)
    print(label)
    print("=" * 80)
    print("TEXT LEN:", len(text))
    print("PART:", repr(part))
    print("PROMPT LEN:", len(prompt))
    print("PROMPT MD5:", hashlib.md5(prompt.encode("utf-8")).hexdigest())


    kwargs = {
        "model": "gemma4:12B",
        "prompt": prompt,
        "options": {
            "temperature": 0.0,
            "top_p": 0.1,
            "num_ctx": 8192,
            "num_predict": 500,
        },
    }

    if use_json_format:
        kwargs["format"] = "json"

    response = ollama.generate(**kwargs)

    print("\nFULL RESPONSE:")
    print(response)

    raw = response.get("response", "")
    print("\nRAW RESPONSE:")
    print(repr(raw))

    print("\nDONE_REASON:", response.get("done_reason", None))
    print("EVAL_COUNT:", response.get("eval_count", None))
    print("PROMPT_EVAL_COUNT:", response.get("prompt_eval_count", None))

    return raw, response


# 1. Same as notebook: with replacement part + JSON mode
raw1, resp1 = debug_generate(
    label="A - WITH PART + JSON FORMAT",
    text=bad_text,
    part=bad_part,
    use_json_format=True
)

# 2. Same as your standalone: no replacement part + JSON mode
raw2, resp2 = debug_generate(
    label="B - NO PART + JSON FORMAT",
    text=bad_text,
    part="",
    use_json_format=True
)

# 3. Test if Ollama JSON mode is the issue
raw3, resp3 = debug_generate(
    label="C - WITH PART + NO JSON FORMAT",
    text=bad_text,
    part=bad_part,
    use_json_format=False
)