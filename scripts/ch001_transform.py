#!/usr/bin/env python3
"""CH001_export → 中間格式（JSONL ＋ schema.json ＋ manifest.json）。

**不依賴 CTOS**，輸出是中性格式，誰都能拿去灌進自己的資料庫。
這支的產出就是要交給同事的東西。

## 欄位名用原始名稱，中文放 schema

JSONL 的 key 是舊系統的原始欄位名（`DGA005`、`JDB007`），不是翻譯過的英文名。
理由有三：資料無損、能對回舊系統畫面、**推不出語意的欄位也照樣保留**。
中文名、型別、依據等級、外鍵都寫在 `schema.json`，顯示層自己去翻。

## 型別轉換

| 來源 | 輸出 | 理由 |
|---|---|---|
| `YYYYMMDD` | `"YYYY-MM-DD"` | 標準日期字串 |
| `YYYY-MM-DD HH:MM:SS.fff` | ISO 8601 | 時間戳 |
| 數值 | **字串** | 金額不走浮點，避免精度損失 |
| 空字串／`0x00` | `null` | NULL 就是 null |
| 其他 | 原樣字串 | 旗標 Y/N/T/F 語意未定，不自作主張轉 bool |

用法：
    ch001_transform.py --src <CH001_export> --out <輸出目錄>
    ch001_transform.py --src <CH001_export> --out out --only stage1
    ch001_transform.py --src <CH001_export> --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ch001_reader import read  # noqa: E402
from ch001_schema import (  # noqa: E402
    col_name, detect_foreign_keys, detect_keys, detect_semantics,
    infer_type, load_dictionary, load_zh_labels, profile_tables,
)

try:
    from ch001_columns import COLUMNS as MANUAL_COLUMNS, MODULE_PREFIX
except ImportError:
    MANUAL_COLUMNS, MODULE_PREFIX = {}, {}

# 階段 1：欄位已定案、三種人各有一塊能驗的表
STAGE1 = [
    # 主檔
    "TPADGA", "TPADFA", "TPADEA", "CRMIKG", "TPADDA", "TPADED", "TPADAA", "TPADBA",
    # 採購
    "JSKJDA", "JSKJDB",
    # 業務
    "JSKKEA", "JSKKEB",
    # 會計
    "KJSNAA", "KJSNBA", "KJSNCA", "KJSNDA", "KJSNFA", "KJSNHB", "KJSNHA",
]

# 已知瑕疵：轉換時挑掉並記進 manifest，不靜默丟
# （見 docs/ch001-export-inventory.md 第三節）
KNOWN_DEFECTS = {
    "KJSNHB": "分錄的傳票總號在 KJSNFA 找不到單頭（2 筆）",
    "JSKJDA": "第 1 列是殘列：無單號、無廠商、無日期，數值欄全為 0，"
              "只有建檔 2007-06-11 與異動 2008-12-08 兩個時間戳（1 筆）",
}

# 這些表的第一欄是單號／代號，空的就是殘列，不是資料
KEY_COL_REQUIRED = {
    "JSKJDA", "JSKJDB", "JSKKEA", "JSKKEB", "KJSNFA", "KJSNHB",
    "TPADGA", "TPADFA", "TPADEA", "TPADDA", "TPADED", "TPADAA", "TPADBA",
    "KJSNAA", "KJSNBA", "KJSNCA", "KJSNDA",
}

DATE_RE = re.compile(r"^(19|20)\d{6}$")
TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?")
NUM_RE = re.compile(r"^-?\.?\d+\.?\d*$")


def convert(value: str, kind: str):
    """單一欄位值 → JSON 可序列化的型別。"""
    if not value:
        return None
    if kind == "date" and DATE_RE.match(value):
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    if kind == "timestamp":
        m = TS_RE.match(value)
        if m:
            y, mo, d, h, mi, s, frac = m.groups()
            micro = (frac or "0").ljust(6, "0")[:6]
            try:
                return datetime(int(y), int(mo), int(d), int(h), int(mi), int(s),
                                int(micro)).isoformat()
            except ValueError:
                return value
    if kind in ("decimal", "period") and NUM_RE.match(value):
        # 金額一律字串：JSON 的 number 是 float，會吃掉精度
        return value
    return value


def build_schema(src: Path, tables: list[str]) -> dict:
    """跑一次推導，組出每張表的欄位定義。"""
    table2func, col2role, _ = load_dictionary(src)
    labels_zh = load_zh_labels(src)
    prof = profile_tables(src)
    keys = detect_keys(prof)
    fks = detect_foreign_keys(prof, keys)

    schema = {}
    for t in tables:
        if t not in prof:
            continue
        info = prof[t]
        cols = []
        for c in info["cols"]:
            name = c["name"]
            man = MANUAL_COLUMNS.get((t, name))
            basis = []
            zh = None
            if man:
                zh, why, level = man
                basis.append(level)
            if (t, name) in labels_zh:
                basis.append("label")
                zh = zh or labels_zh[(t, name)]
            if name in col2role:
                basis.append("dict")
            if (t, name) in fks:
                basis.append("fk")
            if c.get("semantic") and not zh:
                zh = c["semantic"]
                basis.append("rule")
            cols.append({
                "name": name,
                "index": c["idx"],
                "type": c["type"],
                "zh": zh,
                "basis": "+".join(dict.fromkeys(basis)) or None,
                "nullable": c["fill"] < 100,
                "fk": fks[(t, name)][0] if (t, name) in fks else None,
                "note": man[1] if man else None,
            })
        schema[t] = {
            "function": table2func.get(t),
            "module": MODULE_PREFIX.get(t[:3]),
            "rows": info["rows"],
            "primary_key": keys.get(t),
            "columns": cols,
        }
    return schema


def transform(src: Path, out: Path | None, tables: list[str], schema: dict) -> dict:
    """逐表輸出 JSONL；回傳 manifest。"""
    manifest = {
        "source": str(src),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/ch001_transform.py",
        "note": "欄位名為舊系統原始名稱；中文與依據見 schema.json",
        "tables": {},
    }
    for t in tables:
        if t not in schema:
            print(f"  {t:<10} 來源缺檔，跳過", file=sys.stderr)
            continue
        kinds = [c["type"] for c in schema[t]["columns"]]
        names = [c["name"] for c in schema[t]["columns"]]
        fh = (out / f"{t}.jsonl").open("w", encoding="utf-8") if out else None
        n = skipped = blank_key = 0
        widths = set()
        needs_key = t in KEY_COL_REQUIRED
        try:
            for r in read(src / f"{t}.txt"):
                widths.add(len(r))
                if len(r) != len(names):
                    # 欄數不符的列不猜對應關係，整列記下來給人看
                    skipped += 1
                    continue
                if needs_key and not r[0].strip():
                    # 主鍵空白＝舊系統的殘列，跳過但記下來
                    blank_key += 1
                    continue
                obj = {nm: convert(v, k) for nm, v, k in zip(names, r, kinds)}
                if fh:
                    fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
                n += 1
        finally:
            if fh:
                fh.close()
        manifest["tables"][t] = {
            "rows_written": n,
            "rows_skipped_width_mismatch": skipped,
            "rows_skipped_blank_key": blank_key,
            "column_widths_seen": sorted(widths),
            "known_defect": KNOWN_DEFECTS.get(t),
        }
        flags = []
        if skipped: flags.append(f"欄數不符 {skipped}")
        if blank_key: flags.append(f"主鍵空白 {blank_key}")
        flag = f"　跳過：{'、'.join(flags)}" if flags else ""
        print(f"  {t:<10} {n:>9,} 列{flag}", file=sys.stderr)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", help="輸出目錄；不給就是 --dry-run")
    ap.add_argument("--only", choices=["stage1", "all"], default="stage1")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.src)
    if not src.is_dir():
        print(f"找不到目錄：{src}", file=sys.stderr)
        return 2
    out = None if (args.dry_run or not args.out) else Path(args.out)
    if out:
        out.mkdir(parents=True, exist_ok=True)

    tables = STAGE1 if args.only == "stage1" else sorted(
        p.stem for p in src.glob("*.txt") if p.stat().st_size)

    print(f"推導 schema（{len(tables)} 張表）…", file=sys.stderr)
    schema = build_schema(src, tables)
    named = sum(1 for t in schema for c in schema[t]["columns"] if c["zh"])
    total = sum(len(schema[t]["columns"]) for t in schema)
    print(f"  欄位 {total}，有中文名 {named}（{named/total*100:.1f}%）\n", file=sys.stderr)

    print("輸出 JSONL…" if out else "試跑（不寫檔）…", file=sys.stderr)
    manifest = transform(src, out, tables, schema)

    if out:
        (out / "schema.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        total_rows = sum(v["rows_written"] for v in manifest["tables"].values())
        print(f"\n完成：{out}　{len(manifest['tables'])} 張表、{total_rows:,} 列",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
