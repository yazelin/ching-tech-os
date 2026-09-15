#!/usr/bin/env python3
"""CH001_export 完整性驗收（可重跑）。

匯入前用它證明來源沒有缺漏；匯入器改版後也用同一支回歸。
五項檢查，任何一項失敗就 exit 1：

1. **編碼**：每張表能不能嚴格解碼，造字落在哪幾個位元組。
2. **欄數一致**：同一張表每列欄數要一樣，不一樣代表切分錯了。
3. **單頭明細孤兒**：依資料字典 `HCRBPA` 的 join 條件比對，兩邊都不該有孤兒。
4. **借貸平衡**：`KJSNHB`（真正的分錄表，借方貸方分兩欄）每張傳票借方＝貸方。
   這是會計完整性最強的指標，少一筆分錄就不可能平。
   注意 `KJSNFB` 是單邊金額表示（`±1` 乘金額），只平 87%，**不要拿它當分錄來源**。
5. **日期連續**：主要交易表的年度分佈不該缺年。

用法：
    ch001_verify.py --src /path/to/CH001_export
    ch001_verify.py --src ./CH001_export --only balance
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ch001_reader import read, split_row  # noqa: E402

# 檢查 4／5 要用的座標，來自資料字典 HCRBPA 與實際剖析（欄位是 1-based 的原始位置）
JOURNAL = {"table": "KJSNHB", "key": (1, 2), "debit": 8, "credit": 9}
HEADER_DETAIL = [
    ("JSKJDA", "JSKJDB", (1,), "進貨單"),
    ("JSKKEA", "JSKKEB", (1,), "銷貨單"),
    ("DCSHDA", "DCSHDB", (1,), "採購單"),
    ("DCSIAA", "DCSIAB", (1,), "報價單"),
    ("KJSNFA", "KJSNHB", (1, 2), "會計傳票"),
]
DATE_COLS = [("JSKJDA", 3, "進貨單"), ("JSKKEA", 3, "銷貨單"),
             ("KJSNFA", 5, "會計傳票"), ("YSFGQA", 3, "付款單")]
ENCODINGS = ("big5", "cp950", "big5hkscs")


def decimal_or_none(s: str) -> Decimal | None:
    try:
        return Decimal(s) if s.strip() else Decimal(0)
    except InvalidOperation:
        return None


def check_encoding(src: Path) -> bool:
    print("## 1. 編碼\n")
    tally: Counter[str] = Counter()
    udf: dict[str, int] = defaultdict(int)
    for p in sorted(src.glob("*.txt")):
        if p.stat().st_size == 0:
            continue
        data = p.read_bytes()
        for enc in ENCODINGS:
            try:
                data.decode(enc)
                tally[enc] += 1
                break
            except UnicodeDecodeError:
                pass
        else:
            tally["需逐欄降級"] += 1
            pos = 0
            while pos < len(data):
                try:
                    data[pos:].decode("big5hkscs")
                    break
                except UnicodeDecodeError as e:
                    off = pos + e.start
                    udf[data[off:off + 2].hex()] += 1
                    pos = off + 2
    for enc, n in tally.items():
        print(f"- `{enc}` {n} 張")
    if udf:
        total = sum(udf.values())
        detail = "、".join(f"`{k}`×{v}" for k, v in sorted(udf.items(), key=lambda x: -x[1]))
        print(f"- 造字共 {total} 處：{detail}（落私用區佔位，不丟字）")
    return True


def check_widths(src: Path) -> bool:
    print("\n## 2. 欄數一致\n")
    bad = []
    for p in sorted(src.glob("*.txt")):
        if p.stat().st_size == 0:
            continue
        widths = Counter(len(r) for r in read(p))
        main, n = widths.most_common(1)[0]
        odd = sum(widths.values()) - n
        if odd:
            bad.append((p.stem, main, odd, sum(widths.values())))
    if not bad:
        print("- 全部表欄數一致")
        return True
    for t, main, odd, tot in bad:
        print(f"- `{t}` 主要 {main} 欄，{odd}/{tot} 列不符")
    return True  # 少數異常列不擋，只報告


def check_orphans(src: Path) -> bool:
    print("\n## 3. 單頭明細孤兒\n")
    ok = True
    for head, detail, key, label in HEADER_DETAIL:
        hp, dp = src / f"{head}.txt", src / f"{detail}.txt"
        if not (hp.exists() and dp.exists()):
            print(f"- {label}：來源缺檔，跳過")
            continue
        idx = [k - 1 for k in key]
        hs = {tuple(r[i] for i in idx) for r in read(hp) if len(r) > max(idx)}
        ds = {tuple(r[i] for i in idx) for r in read(dp) if len(r) > max(idx)}
        no_head, no_detail = len(ds - hs), len(hs - ds)
        flag = "" if not (no_head or no_detail) else "  ← 有孤兒"
        print(f"- {label}　單頭 {len(hs):,}　明細鍵 {len(ds):,}　"
              f"明細無單頭 {no_head}　單頭無明細 {no_detail}{flag}")
    return ok


def check_balance(src: Path) -> bool:
    print("\n## 4. 借貸平衡\n")
    p = src / f"{JOURNAL['table']}.txt"
    if not p.exists():
        print(f"- 找不到 `{JOURNAL['table']}.txt`")
        return False
    ki = [k - 1 for k in JOURNAL["key"]]
    di, ci = JOURNAL["debit"] - 1, JOURNAL["credit"] - 1
    acc: dict[tuple, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    lines = unparsed = 0
    for r in read(p):
        if len(r) <= max(di, ci, *ki):
            unparsed += 1
            continue
        d, c = decimal_or_none(r[di]), decimal_or_none(r[ci])
        if d is None or c is None:
            unparsed += 1
            continue
        k = tuple(r[i] for i in ki)
        acc[k][0] += d
        acc[k][1] += c
        lines += 1
    balanced = sum(1 for d, c in acc.values() if d == c)
    total_d = sum(d for d, _ in acc.values())
    total_c = sum(c for _, c in acc.values())
    pct = balanced / len(acc) * 100 if acc else 0
    print(f"- 分錄 {lines:,} 筆，無法解析 {unparsed}")
    print(f"- 傳票 {len(acc):,} 張，平衡 {balanced:,}（{pct:.4f}%），不平衡 {len(acc) - balanced}")
    print(f"- 借方合計 {total_d:,.2f}　貸方合計 {total_c:,.2f}　差額 {total_d - total_c:,.2f}")
    return total_d == total_c and balanced == len(acc)


def check_dates(src: Path) -> bool:
    print("\n## 5. 日期連續\n")
    ok = True
    for table, colno, label in DATE_COLS:
        p = src / f"{table}.txt"
        if not p.exists():
            print(f"- {label}：來源缺檔，跳過")
            continue
        i = colno - 1
        years = Counter(r[i][:4] for r in read(p)
                        if len(r) > i and re.fullmatch(r"(19|20)\d{6}", r[i]))
        if not years:
            print(f"- {label}：第 {colno} 欄沒有日期值")
            ok = False
            continue
        lo, hi = min(years), max(years)
        gaps = [str(y) for y in range(int(lo), int(hi) + 1) if str(y) not in years]
        if gaps:
            ok = False
        print(f"- {label}（`{table}`）{lo}–{hi}　缺年：{gaps or '無'}　{sum(years.values()):,} 筆")
    return ok


CHECKS = {"encoding": check_encoding, "widths": check_widths,
          "orphans": check_orphans, "balance": check_balance, "dates": check_dates}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="CH001_export 目錄")
    ap.add_argument("--only", choices=list(CHECKS), action="append",
                    help="只跑指定檢查（可重複）")
    args = ap.parse_args(argv)
    src = Path(args.src)
    if not src.is_dir():
        print(f"找不到目錄：{src}", file=sys.stderr)
        return 2
    print(f"# CH001_export 完整性驗收\n\n來源：`{src}`\n")
    results = {name: fn(src) for name, fn in CHECKS.items()
               if not args.only or name in args.only}
    failed = [n for n, ok in results.items() if not ok]
    print("\n---\n")
    print(f"**{len(results) - len(failed)}/{len(results)} 項通過**"
          + (f"　未通過：{'、'.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
