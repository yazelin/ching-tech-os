#!/usr/bin/env python3
"""CH001_export 全表盤點：資料字典 + 欄位推斷 → `docs/ch001-export-inventory.md`。

輸出刻意不含真實客戶／廠商名，只有表名、功能、筆數、欄位樣式統計，
所以產出可以直接進公開 repo（進版控前仍須用 ERPNext 名單反向掃一次）。

用法：
    ch001_inventory.py <CH001_export 目錄> > docs/ch001-export-inventory.md
"""
import re, sys, json
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent))
from ch001_reader import read as b5read

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "ch001")
MAXROWS = 20000          # 大檔只讀前 N 列就夠推欄位

# ---------- 1. 讀資料字典 HCRBPA / HCRBPB ----------
def read_rows(p, limit=None):
    # Big5 感知切分：不能先 decode 再 split（0x7C 可能是中文字的低位元組）
    return list(b5read(p, limit=limit, max_bytes=40_000_000 if limit else None))

table2func = {}
func_order = []
for dict_file in ("HCRBPA.txt", "HCRBPB.txt"):
    p = SRC / dict_file
    if not p.exists(): continue
    for r in read_rows(p):
        if len(r) < 6: continue
        func = r[2].strip()
        if not func: continue
        func_order.append(func)
        for tok in re.findall(r"\b([A-Z]{4,6})\b", r[5]):
            table2func.setdefault(tok, func)

# ---------- 2. 欄位樣式推斷 ----------
PATTERNS = [
    ("日期",     re.compile(r"^(19|20)\d{6}$")),
    ("年月",     re.compile(r"^(19|20)\d{4}$")),
    ("時間戳",   re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}")),
    ("旗標",     re.compile(r"^[YNTF]$")),
    ("數值",     re.compile(r"^-?\.?\d+\.?\d*$")),
    ("email",    re.compile(r"^[\w.+-]+@[\w.-]+$")),
    ("電話",     re.compile(r"^[\d()\-\s#]{8,}$")),
    ("單號",     re.compile(r"^[A-Z]{2}\d{10,}$")),
    ("代號",     re.compile(r"^[A-Z]{1,4}\d{2,}$")),
    ("中文",     re.compile(r"[一-鿿]")),
]
def kind_of(vals):
    s = vals[:300]
    for name, rx in PATTERNS:
        if sum(1 for v in s if rx.search(v)) / len(s) > 0.9: return name
    return "文字"

def profile(p):
    rows = read_rows(p, MAXROWS)
    if not rows: return None
    ncol = max(len(r) for r in rows)
    cols = []
    for i in range(ncol):
        vals = [r[i].strip() for r in rows if i < len(r) and r[i].strip()]
        if not vals:
            cols.append(None); continue
        cols.append({
            "i": i + 1, "fill": round(len(vals) / len(rows) * 100),
            "uniq": len(set(vals)), "kind": kind_of(vals),
            "unique_key": len(set(vals)) == len(rows) and len(rows) > 1,
            "maxlen": max(len(v) for v in vals),
        })
    return {"rows": len(rows), "truncated": len(rows) >= MAXROWS, "ncol": ncol, "cols": cols}

# ---------- 3. 跑全表 ----------
results = {}
for p in sorted(SRC.glob("*.txt")):
    if p.stat().st_size == 0: continue
    r = profile(p)
    if r: results[p.stem] = r

# ---------- 4. 輸出 ----------
by_func = defaultdict(list)
for t, r in results.items():
    by_func[table2func.get(t, "（字典未收錄）")].append((t, r))

print(f"# CH001_export 全表盤點\n")
print(f"來源：`smb://192.168.11.6/d/CH001_export`（鼎新 Workflow ERP 整庫傾印）")
print(f"格式：Big5、`|` 分隔、無標題列、`0x00` 表 NULL、CRLF 換行\n")
print(f"有資料的表 **{len(results)}** 張；資料字典 `HCRBPA`／`HCRBPB` 收錄 **{len(table2func)}** 個表名，"
      f"對應 **{len(set(table2func.values()))}** 種功能。\n")
print(f"欄位推斷只讀每張表前 {MAXROWS:,} 列；`截斷` 標記者實際列數更多。\n")

seen = set()
for func in list(dict.fromkeys(func_order)) + ["（字典未收錄）"]:
    if func in seen or func not in by_func: continue
    seen.add(func)
    print(f"\n## {func}\n")
    for t, r in sorted(by_func[func]):
        trunc = "　**截斷**" if r["truncated"] else ""
        print(f"### {t}　{r['rows']:,} 列 × {r['ncol']} 欄{trunc}\n")
        keys = [c for c in r["cols"] if c and c["unique_key"]]
        if keys: print(f"唯一鍵候選：第 {'、'.join(str(c['i']) for c in keys)} 欄\n")
        parts = []
        for c in r["cols"]:
            if c is None: continue
            if c["fill"] < 5: continue
            parts.append(f"{c['i']}:{c['kind']}({c['fill']}%/{c['uniq']}種)")
        print("　".join(parts) + "\n")
        nempty = sum(1 for c in r["cols"] if c is None)
        if nempty: print(f"（另有 {nempty} 欄全空）\n")

json.dump({t: r for t, r in results.items()}, open("inventory.json", "w"), ensure_ascii=False)
