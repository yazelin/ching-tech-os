#!/usr/bin/env python3
"""CH001_export 單張表的欄位剖析：無標題列，只能從值本身推欄位語意。

搭配資料字典 `HCRBPA`（表名→功能→join 條件）使用；推出來的語意要再用
已知來源交叉驗證才算數（例：`TPADGA` 第 5 欄與 ERPNext `tax_id` 91.5% 命中，
才確定它是統一編號）。

用法：
    ch001_profile.py <檔案>                # 樣本值遮罩
    ch001_profile.py <檔案> --show-values  # 顯示原值，勿用於要進 repo 的輸出
"""
import sys, re, collections
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ch001_reader import read

path = Path(sys.argv[1])
show = "--show-values" in sys.argv
rows = list(read(path))
ncol = max(len(r) for r in rows)

PATTERNS = [
    ("日期 yyyymmdd", re.compile(r"^(19|20)\d{6}$")),
    ("年月 yyyymm",   re.compile(r"^(19|20)\d{4}$")),
    ("時間戳",        re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}")),
    ("旗標 Y/N/T/F",  re.compile(r"^[YNTF]$")),
    ("小數",          re.compile(r"^-?\.?\d+\.?\d*$")),
    ("email",         re.compile(r"^[\w.+-]+@[\w.-]+$")),
    ("電話",          re.compile(r"^[\d()\-\s#轉]{7,}$")),
    ("代號 英數",     re.compile(r"^[A-Z]{1,4}\d{2,}$")),
    ("含中文",        re.compile(r"[一-鿿]")),
]
def mask(v):
    if len(v) <= 2: return v
    return v[0] + "…" + v[-1] if re.search(r"[一-鿿]", v) else v[:3] + "…"

print(f"# {path.stem}　{len(rows)} 列 × {ncol} 欄\n")
print(f"{'#':>3} {'非空':>6} {'相異':>6} {'長度':>7}  {'推測樣式':<14} 樣本")
for i in range(ncol):
    vals = [r[i].strip() for r in rows if i < len(r)]
    nz = [v for v in vals if v]
    if not nz:
        print(f"{i+1:>3} {'0':>6} {'-':>6} {'-':>7}  {'(全空)':<14}")
        continue
    uniq = len(set(nz))
    lens = [len(v) for v in nz]
    kind = "自由文字"
    for name, rx in PATTERNS:
        if sum(1 for v in nz[:400] if rx.search(v)) / min(len(nz), 400) > 0.9:
            kind = name; break
    key = "  ← 唯一鍵" if uniq == len(rows) and len(rows) > 1 else ""
    samp = ", ".join((v if show else mask(v)) for v in list(dict.fromkeys(nz))[:3])
    print(f"{i+1:>3} {len(nz):>6} {uniq:>6} {min(lens)}-{max(lens):>4}  {kind:<14} {samp[:60]}{key}")
