#!/usr/bin/env python3
"""中間格式（JSONL ＋ schema.json）→ PostgreSQL 的 `ch001` schema。

只依賴連線字串，不依賴 CTOS。資料放獨立的 `ch001` schema，不進 `public`：
不污染正式表、唯讀帳號只授這個 schema、這版不要了就
`DROP SCHEMA ch001 CASCADE` 一句話收乾淨。

## 中文寫進資料庫，不是只寫在文件裡

每張表與每個欄位都下 `COMMENT ON`，內容是中文名加依據等級。
會計、採購、業務用 DBeaver、pgAdmin 或任何 SQL 工具打開就看得到
「統一編號 [verified]」這種說明，不必等前端做好。推不出語意的欄位
留原始名稱，註解寫型別與填充率，讓看的人自己認。

## 型別

| 中間格式 | PostgreSQL | 理由 |
|---|---|---|
| date | `date` | |
| timestamp | `timestamp` | 舊系統沒有時區資訊，不用 timestamptz |
| decimal／period | `numeric` | 金額不走浮點 |
| 其他 | `text` | 旗標 Y/N/T/F 語意未定，不轉 boolean |

用法：
    ch001_load.py --src <中間格式目錄> --dsn postgresql://… --ddl-only
    ch001_load.py --src <中間格式目錄> --dsn postgresql://… --load
    ch001_load.py --src <中間格式目錄> --ddl-only > ch001_schema.sql   # 不連線，只印 DDL
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

PG_TYPE = {"date": "date", "timestamp": "timestamp", "flag": "text", "text": "text",
           "text_zh": "text", "code": "text", "docno": "text", "email": "text",
           "phone": "text", "empty": "text"}

# `decimal` 預設給 text，只有確定要拿來加總的才升為 numeric。
# 理由：統一編號、傳票總號、郵遞區號、類別代碼在來源都是純數字，
# 用 numeric 會丟掉前導 0 也讓語意走樣（統編是識別碼不是數量）。
# 寧可保守 —— text 一樣查得動，需要時 ::numeric 就好；反過來丟掉的資料要不回來。
NUMERIC_HINTS = ("金額", "數量", "單價", "餘額", "合計", "借方", "貸方", "價", "稅", "天數")


def pg_type(col: dict) -> str:
    if col["type"] in PG_TYPE:
        return PG_TYPE[col["type"]]
    if col["type"] in ("decimal", "period"):
        zh = col.get("zh") or ""
        if col.get("fk") or col.get("primary"):
            return "text"
        return "numeric" if any(h in zh for h in NUMERIC_HINTS) else "text"
    return "text"


def quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def build_ddl(schema: dict) -> str:
    """從 schema.json 產出完整 DDL，含中文註解與索引。"""
    out: list[str] = [
        "-- 舊 ERP（鼎新 e-Go）歷史資料查核用 schema。由 scripts/ch001_load.py 產生。",
        "-- 唯讀性質：這批是已結束系統的歷史，不開寫入路徑。",
        "-- 不要了就 DROP SCHEMA ch001 CASCADE。",
        "",
        "CREATE SCHEMA IF NOT EXISTS ch001;",
        "",
    ]
    for table, info in schema.items():
        cols = info["columns"]
        lines = []
        pk_names = set(info.get("primary_key") or [])
        for c in cols:
            c["primary"] = c["name"] in pk_names
            lines.append(f'    "{c["name"].lower()}" {pg_type(c)}')
        out.append(f'DROP TABLE IF EXISTS ch001."{table.lower()}";')
        out.append(f'CREATE TABLE ch001."{table.lower()}" (')
        out.append(",\n".join(lines))
        out.append(");")

        # 表註解：中文功能 ＋ 模組 ＋ 列數
        bits = [x for x in (info.get("function"), info.get("module")) if x]
        label = "／".join(dict.fromkeys(bits)) or "（資料字典未收錄）"
        out.append(f'COMMENT ON TABLE ch001."{table.lower()}" IS '
                   f'{quote(f"{label}　來源 {info["rows"]:,} 列")};')

        # 欄位註解：中文名 ＋ 依據等級；推不出語意的寫型別與填充率
        for c in cols:
            if c["zh"]:
                note = f"{c['zh']} [{c['basis']}]" if c["basis"] else c["zh"]
                if c.get("fk"):
                    note += f" → {c['fk']}"
            else:
                fill = "" if c["nullable"] is False else "可為空"
                note = f"（語意未定）{c['type']}{'　' + fill if fill else ''}"
            out.append(f'COMMENT ON COLUMN ch001."{table.lower()}"."{c["name"].lower()}" '
                       f'IS {quote(note)};')

        # 索引：主鍵、外鍵、日期欄。查核一定會用單號與日期查
        pk = info.get("primary_key")
        if pk:
            cl = ", ".join(f'"{x.lower()}"' for x in pk)
            out.append(f'CREATE UNIQUE INDEX ON ch001."{table.lower()}" ({cl});')
        for c in cols:
            if c is cols[0] and not pk:
                out.append(f'CREATE INDEX ON ch001."{table.lower()}" ("{c["name"].lower()}");')
            elif c.get("fk") or c["type"] == "date":
                out.append(f'CREATE INDEX ON ch001."{table.lower()}" ("{c["name"].lower()}");')
        out.append("")
    return "\n".join(out)


def copy_table(conn, table: str, cols: list[dict], path: Path) -> int:
    """用 COPY 灌一張表。31 萬筆分錄逐筆 INSERT 會跑到天亮。"""
    names = [c["name"] for c in cols]
    buf = io.StringIO()
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            obj = json.loads(line)
            cells = []
            for nm in names:
                v = obj.get(nm)
                if v is None:
                    cells.append("\\N")
                else:
                    cells.append(str(v).replace("\\", "\\\\").replace("\t", "\\t")
                                 .replace("\n", "\\n").replace("\r", "\\r"))
            buf.write("\t".join(cells) + "\n")
            n += 1
    buf.seek(0)
    collist = ", ".join(f'"{x.lower()}"' for x in names)
    with conn.cursor() as cur:
        cur.copy_expert(f'COPY ch001."{table.lower()}" ({collist}) FROM STDIN', buf)
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="中間格式目錄（含 schema.json）")
    ap.add_argument("--dsn", help="PostgreSQL 連線字串；不給就只印 DDL")
    ap.add_argument("--ddl-only", action="store_true")
    ap.add_argument("--load", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.src)
    schema = json.loads((src / "schema.json").read_text(encoding="utf-8"))
    ddl = build_ddl(schema)

    if not args.dsn or args.ddl_only:
        print(ddl)
        if not args.dsn:
            return 0

    import psycopg2  # noqa: PLC0415  （只在真的要連線時才需要）
    conn = psycopg2.connect(args.dsn)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            print("建立 schema 與資料表…", file=sys.stderr)
            cur.execute(ddl)
        conn.commit()
        if args.load:
            total = 0
            for table, info in schema.items():
                p = src / f"{table}.jsonl"
                if not p.exists():
                    print(f"  {table:<10} 缺 JSONL，跳過", file=sys.stderr)
                    continue
                n = copy_table(conn, table, info["columns"], p)
                conn.commit()
                total += n
                print(f"  {table:<10} {n:>9,} 列", file=sys.stderr)
            print(f"\n完成：{len(schema)} 張表、{total:,} 列", file=sys.stderr)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
