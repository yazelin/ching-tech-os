"""CTOS HTTP API 客戶端（純 stdlib）"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    """API 錯誤"""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


def request(
    url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    json_body: dict | None = None,
    params: dict | None = None,
    raw: bool = False,
):
    """送出 API 請求

    Args:
        url: 服務基底網址（如 https://ching-tech.ddns.net/ctos）
        path: API 路徑（如 /api/knowledge/kb-182）
        method: HTTP 方法
        token: Bearer token
        json_body: JSON request body
        params: query 參數（值為 list 時展開為重複參數）
        raw: True 時回傳 bytes，否則解析 JSON

    Returns:
        dict（JSON）或 bytes（raw=True）

    Raises:
        ApiError: HTTP 錯誤
    """
    full = url.rstrip("/") + path
    if params:
        pairs = []
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                pairs.extend((key, v) for v in value)
            else:
                pairs.append((key, value))
        if pairs:
            full += "?" + urllib.parse.urlencode(pairs)

    # 路徑可能含中文，先做百分比編碼（保留 :/?&= 等結構字元）
    full = urllib.parse.quote(full, safe=":/?&=%+")

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(full, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
            detail = payload.get("detail") or payload.get("error") or str(payload)
        except Exception:
            detail = e.reason or str(e)
        raise ApiError(e.code, detail) from None
    except urllib.error.URLError as e:
        print(f"連線失敗：{e.reason}（檢查網址或網路）", file=sys.stderr)
        sys.exit(2)

    if raw:
        return body
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))
