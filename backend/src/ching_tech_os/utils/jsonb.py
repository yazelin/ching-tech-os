"""json / jsonb 欄位的讀取輔助

`database.py` 為每條連線註冊了 json / jsonb codec（encoder 是 `json.dumps`），
所以**寫入端一律直接傳 Python dict/list**，不可以自己先 `json.dumps` 再傳給
`$n::jsonb`——那會被 codec 再編碼一次，欄位裡存進去的是一個 JSON 字串純量
（`jsonb_typeof` = `string`），SQL 端的 `->`、`||` 全部失效。

讀取端則可能同時遇到兩種資料：修好之後寫入的正常物件，以及舊版雙重編碼留下的
字串。這裡的函式把兩種都轉回 Python 物件。
"""

import json
from typing import Any

__all__ = ["parse_json_field", "parse_json_dict"]


def parse_json_field(value: Any, default: Any = None) -> Any:
    """把 json/jsonb 欄位的值轉成 Python 物件

    Args:
        value: asyncpg 回傳的值（正常是 dict/list，舊資料可能是字串）
        default: 值為 None 或無法解析時回傳的預設值

    Returns:
        解析後的 Python 物件
    """
    if value is None:
        return default
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return default
    return value


def parse_json_dict(value: Any) -> dict:
    """把 json/jsonb 欄位的值轉成 dict，不是 dict 一律當成空的

    被 `||` 串壞的資料（例如 `[{}, "{\\"theme\\": \\"light\\"}"]`）會回 `{}`，
    避免壞掉的列讓呼叫端炸開。
    """
    parsed = parse_json_field(value)
    return parsed if isinstance(parsed, dict) else {}
