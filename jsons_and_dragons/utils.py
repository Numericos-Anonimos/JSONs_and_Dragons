import math
import re
from typing import Any, Dict, List


def get_nested(data: Dict, path: str, default: Any = None) -> Any:
    keys = path.split(".")
    curr = data
    try:
        for key in keys:
            if isinstance(curr, dict):
                curr = curr.get(key)
            elif isinstance(curr, list) and key.isdigit():
                curr = curr[int(key)]
            else:
                return default
            if curr is None:
                return default
        return curr
    except Exception:
        return default


def set_nested(data: Dict, path: str, value: Any) -> None:
    keys = path.split(".")
    curr = data
    for i, key in enumerate(keys[:-1]):
        if key not in curr:
            curr[key] = {}
        curr = curr[key]
    curr[keys[-1]] = value


def resolve_value(value: Any, context: Dict) -> Any:
    if callable(value):
        try:
            return value(context)
        except RecursionError:
            return 0
    return value


def interpolate_and_eval(text: str, context: Dict) -> Any:
    if not isinstance(text, str):
        return resolve_value(text, context)
    pattern = re.compile(
        r"\{([^}]+)\}"
    )  # pattern = re.compile(r'\{([a-zA-Z0-9_.]+)\}')

    def replacer(match):
        path = match.group(1)
        raw_val = get_nested(context, path)
        val = resolve_value(raw_val, context)
        return "0" if val is None else str(val)

    interpolated = pattern.sub(replacer, text)
    if any(c in interpolated for c in "+-*/") or "floor" in interpolated:
        try:
            safe_dict = {
                "floor": math.floor,
                "ceil": math.ceil,
                "max": max,
                "min": min,
                "abs": abs,
            }
            return eval(interpolated, {"__builtins__": None}, safe_dict)
        except Exception:
            pass
    try:
        if "." in interpolated:
            return float(interpolated)
        return int(interpolated)
    except ValueError:
        return interpolated
