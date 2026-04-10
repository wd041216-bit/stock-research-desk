from __future__ import annotations

import json
import re
from typing import Any


def parse_structured_response(raw: str) -> tuple[dict[str, Any], bool]:
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        pass

    cleaned = strip_markdown_fences(raw)
    try:
        return json.loads(cleaned), True
    except json.JSONDecodeError:
        pass

    extracted = extract_json_object(cleaned)
    if extracted:
        try:
            return json.loads(extracted), True
        except json.JSONDecodeError:
            balanced = balance_braces(extracted)
            return json.loads(balanced), True

    balanced = balance_braces(cleaned)
    return json.loads(balanced), True


def strip_markdown_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


def extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1:
        return None
    if end == -1 or end <= start:
        return text[start:]
    return text[start : end + 1]


def balance_braces(text: str) -> str:
    text = text.strip()
    if "{" not in text:
        raise json.JSONDecodeError("No JSON object start found", text, 0)
    open_count = text.count("{")
    close_count = text.count("}")
    if close_count < open_count:
        text = text + ("}" * (open_count - close_count))
    return text
