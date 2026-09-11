#!/usr/bin/env python3
"""把 ERPNext 的業務 doctype 逐筆匯成 JSON 與 CSV（停用 ERPNext 前的可讀備份）。

只用標準函式庫，走 ERPNext REST API（`/api/resource`），憑證讀環境變數
ERPNEXT_URL / ERPNEXT_API_KEY / ERPNEXT_API_SECRET，或用 --env-file 指定 .env
（只抓這三個 key，不 source 整個檔案）。

輸出：
  <out>/<Doctype>.json   完整文件陣列（含子表）
  <out>/<Doctype>.csv    父層純量欄位（子表不進 CSV）
  <out>/manifest.json    每個 doctype 的筆數、匯出時間、失敗清單

用法：
  erpnext_export.py --out /mnt/nas/ctos/erpnext-backup/20260912/doctypes
  erpnext_export.py --env-file /home/ct/SDD/ching-tech-os/.env --out ./out --doctypes Supplier Customer
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# 業務資料。系統表（DocType、DocField、Role、Workspace…）由 bench backup 的 SQL dump 涵蓋。
DEFAULT_DOCTYPES = [
    # 往來對象
    "Supplier", "Customer", "Contact", "Address", "Supplier Group", "Customer Group",
    "Territory", "Industry Type", "Lead", "Opportunity",
    # 物料與庫存
    "Item", "Item Group", "Item Price", "Item Attribute", "UOM",
    "Warehouse", "Bin", "Stock Ledger Entry", "Stock Entry", "Stock Reconciliation",
    "Material Request", "BOM",
    # 採購與銷售單據
    "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Supplier Quotation",
    "Quotation", "Sales Order", "Delivery Note", "Sales Invoice",
    # 專案
    "Project", "Task", "Project Type", "Timesheet",
    # 其他
    "Company", "Comment", "File", "User", "Note", "ToDo", "Event",
]

# 這些 doctype 沒有 name 以外的清單欄位限制；子表不能直接列，跳過
SKIP_IF_MISSING = True


class Erp:
    def __init__(self, url: str, key: str, secret: str, timeout: int = 60):
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"token {key}:{secret}", "Accept": "application/json"}
        self.timeout = timeout

    def _get(self, path: str, retries: int = 3) -> dict:
        req = urllib.request.Request(self.url + path, headers=self.headers)
        last: Exception | None = None
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                # 404 = doctype 不存在或無此筆；403 = 沒權限；都不重試
                if e.code in (403, 404):
                    raise
                last = e
            except (urllib.error.URLError, TimeoutError) as e:
                last = e
            time.sleep(1.5 * (attempt + 1))
        assert last is not None
        raise last

    def names(self, doctype: str) -> list[str]:
        q = urllib.parse.urlencode({"fields": json.dumps(["name"]), "limit_page_length": 0})
        data = self._get(f"/api/resource/{urllib.parse.quote(doctype)}?{q}")["data"]
        return [row["name"] for row in data]

    def doc(self, doctype: str, name: str) -> dict:
        return self._get(f"/api/resource/{urllib.parse.quote(doctype)}/{urllib.parse.quote(name, safe='')}")["data"]


def read_env_file(path: Path) -> dict[str, str]:
    """只取 ERPNEXT_* 三個 key，不 source（.env 裡有些行 bash 會當指令跑）。"""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("ERPNEXT_") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def write_csv(path: Path, docs: list[dict]) -> None:
    scalar_keys: list[str] = []
    seen: set[str] = set()
    for d in docs:
        for k, v in d.items():
            if isinstance(v, (list, dict)) or k in seen:
                continue
            seen.add(k)
            scalar_keys.append(k)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=scalar_keys, extrasaction="ignore")
        w.writeheader()
        for d in docs:
            w.writerow({k: d.get(k, "") for k in scalar_keys})


def export(erp: Erp, doctypes: list[str], out: Path, log=print) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": erp.url,
        "doctypes": {},
        "failed": [],
    }
    for dt in doctypes:
        t0 = time.time()
        try:
            names = erp.names(dt)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404) and SKIP_IF_MISSING:
                # 404 = 沒這個 doctype；403 = API 使用者沒讀取權限。兩者都由 bench backup 的 SQL dump 涵蓋，記下來不算失敗
                log(f"[skip] {dt}: HTTP {e.code}")
                manifest["doctypes"][dt] = {"count": None, "note": f"skipped: HTTP {e.code}"}
                continue
            manifest["failed"].append({"doctype": dt, "error": f"list {e.code}"})
            log(f"[fail] {dt}: list {e.code}")
            continue
        docs: list[dict] = []
        errors = 0
        for n in names:
            try:
                docs.append(erp.doc(dt, n))
            except Exception as e:  # noqa: BLE001 - 單筆失敗記下來繼續，備份要盡量完整
                errors += 1
                manifest["failed"].append({"doctype": dt, "name": n, "error": str(e)[:200]})
        safe = dt.replace(" ", "_")
        (out / f"{safe}.json").write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
        if docs:
            write_csv(out / f"{safe}.csv", docs)
        manifest["doctypes"][dt] = {"count": len(docs), "listed": len(names), "errors": errors, "seconds": round(time.time() - t0, 1)}
        log(f"[ok] {dt}: {len(docs)}/{len(names)} 筆，錯 {errors}，{time.time() - t0:.1f}s")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="輸出目錄")
    ap.add_argument("--env-file", help="從 .env 讀 ERPNEXT_URL / ERPNEXT_API_KEY / ERPNEXT_API_SECRET")
    ap.add_argument("--doctypes", nargs="*", help="只匯這些 doctype（預設是內建業務清單）")
    args = ap.parse_args(argv)

    env = dict(os.environ)
    if args.env_file:
        env.update(read_env_file(Path(args.env_file)))
    missing = [k for k in ("ERPNEXT_URL", "ERPNEXT_API_KEY", "ERPNEXT_API_SECRET") if not env.get(k)]
    if missing:
        print(f"缺少環境變數：{', '.join(missing)}", file=sys.stderr)
        return 2

    erp = Erp(env["ERPNEXT_URL"], env["ERPNEXT_API_KEY"], env["ERPNEXT_API_SECRET"])
    manifest = export(erp, args.doctypes or DEFAULT_DOCTYPES, Path(args.out))
    total = sum((v.get("count") or 0) for v in manifest["doctypes"].values())
    print(f"完成：{len(manifest['doctypes'])} 個 doctype，共 {total} 筆，失敗 {len(manifest['failed'])} 項")
    return 1 if manifest["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
