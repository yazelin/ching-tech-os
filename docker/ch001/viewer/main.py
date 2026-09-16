"""舊 ERP 歷史資料查核頁（唯讀）。

給會計、採購、業務用瀏覽器核對舊系統資料，不必裝 DBeaver。

設計上只做三件事：列出表、瀏覽與搜尋、從單頭鑽到明細。沒有新增修改刪除 ——
這是查核工具，資料是已結束系統的歷史。

**中文欄位名直接讀資料庫的 COMMENT**（`col_description`），不在這裡維護第二份
對照表。來源是 `scripts/ch001_columns.py` 與自動推導，經 `ch001_load.py` 寫進
資料庫，所以三邊永遠一致；改了對照重跑載入，畫面自動跟著變。

連線一律走唯讀帳號，且每個請求都開 read-only transaction —— 就算有人在這裡
寫出 UPDATE，資料庫那層也會擋下來。
"""
from __future__ import annotations

import os
import re
import secrets
from html import escape

import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

DSN = os.environ["CH001_VIEWER_DSN"]
USER = os.environ.get("CH001_VIEWER_USER", "ct")
PASSWORD = os.environ["CH001_VIEWER_PASSWORD"]
PAGE_SIZE = 50

# 單頭 → 明細的對應。鑽取用，寫死比猜可靠。
DETAILS = {
    "jskjda": ("jskjdb", ("jda001",), ("jdb001",)),
    "jskkea": ("jskkeb", ("kea001",), ("keb001",)),
    "kjsnfa": ("kjsnhb", ("nfa001", "nfa002"), ("nhb001", "nhb002")),
}
# 單頭表的主鍵欄。會計傳票是 (類別, 總號) 複合鍵 —— 只用第一欄當 key 會抓到
# 一整批同類別的傳票而不是指定那張，所以網址用「~」把多欄串起來。
HEAD_KEYS = {t: v[1] for t, v in DETAILS.items()}
KEY_SEP = "~"
SAFE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

app = FastAPI(title="舊 ERP 歷史資料查核", docs_url=None, redoc_url=None)
security = HTTPBasic()


def auth(cred: HTTPBasicCredentials = Depends(security)) -> str:
    ok = secrets.compare_digest(cred.username, USER) and \
        secrets.compare_digest(cred.password, PASSWORD)
    if not ok:
        raise HTTPException(401, "帳號或密碼錯誤",
                            {"WWW-Authenticate": "Basic"})
    return cred.username


def query(sql: str, args=()):
    """一律在 read-only transaction 裡查，多一層保險。"""
    with psycopg2.connect(DSN) as conn:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, args)
            return cur.fetchall()


def ident(name: str) -> str:
    """表名與欄位名只允許小寫識別字；不合的直接拒絕，不做跳脫。"""
    if not SAFE_NAME.match(name):
        raise HTTPException(400, "名稱不合法")
    return name


CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 system-ui,"Noto Sans TC",sans-serif;color:#1a1a1a;background:#f6f7f9}
header{background:#22303f;color:#fff;padding:12px 20px;display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
header a{color:#9fd0ff;text-decoration:none}
header h1{font-size:16px;margin:0;font-weight:600}
main{padding:20px;max-width:100%}
h2{font-size:15px;margin:22px 0 8px}
.mod{color:#666;font-size:12px}
table{border-collapse:collapse;background:#fff;font-size:13px}
th,td{border:1px solid #dfe3e8;padding:5px 9px;text-align:left;white-space:nowrap;
      max-width:340px;overflow:hidden;text-overflow:ellipsis}
th{background:#eef1f4;position:sticky;top:0;font-weight:600}
th small{display:block;font-weight:400;color:#7a8794;font-size:11px}
.wrap{overflow:auto;max-height:76vh;border:1px solid #dfe3e8;border-radius:4px;background:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:10px}
.card{background:#fff;border:1px solid #dfe3e8;border-radius:4px;padding:10px 12px}
.card a{font-weight:600;text-decoration:none;color:#16528c}
.card .n{color:#6b7684;font-size:12px}
.bar{display:flex;gap:10px;align-items:center;margin:10px 0;flex-wrap:wrap}
input[type=search]{padding:6px 10px;border:1px solid #c9d0d8;border-radius:4px;min-width:240px;font-size:13px}
button,.btn{padding:6px 12px;border:1px solid #c9d0d8;background:#fff;border-radius:4px;
            cursor:pointer;text-decoration:none;color:#1a1a1a;font-size:13px}
.btn[aria-disabled=true]{opacity:.4;pointer-events:none}
.undef{color:#a0a8b0;font-weight:400}
th.undef{color:#a0a8b0}
.kv{max-width:760px}
.kv th{width:190px;text-align:right;vertical-align:top}
.kv td{white-space:normal;max-width:560px}
.wrap.fit{display:inline-block;max-width:100%}
.note{color:#6b7684;font-size:12px;margin:6px 0 14px}
td a{color:#16528c}
"""


# 這些是從資料形狀推出來的「型別」，不是業務語意。畫面上跟「語意未定」同等對待 ——
# 標成「是否旗標」會讓人以為那就是欄位名稱，反而妨礙他們指出真正的名字。
TYPE_ONLY_LABELS = {"是否旗標", "金額／數量", "建檔／異動時間", "日期", "年月"}


def table_label(desc: str, fallback: str) -> str:
    """表卡片只顯示功能名，不帶模組與列數。

    註解格式是「功能1／功能2／模組　來源 N 列」，模組已經是分組標題了，
    再印一次只是把卡片撐長。
    """
    if not desc:
        return fallback
    return desc.split("　")[0] or fallback


def th(c) -> str:
    """表頭儲存格：認得出來就「中文名／原欄位名」兩行，認不出來只印一次欄位名。

    兩種情況都補 <small> 的話，未認出的欄位會上下印同一個名字兩遍。
    """
    zh = (c["zh"] or "").split(" [")[0]
    if zh and not zh.startswith("（語意未定）") and zh not in TYPE_ONLY_LABELS:
        return f"<th>{escape(zh)}<small>{escape(c['name'])}</small></th>"
    return f"<th class=undef>{escape(c['name'])}</th>"


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html lang=zh-Hant><meta charset=utf-8>"
        f"<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)}</title><style>{CSS}</style>"
        f"<header><h1>舊 ERP 歷史資料查核</h1>"
        f"<a href='/'>回表清單</a>"
        f"<span class=mod>唯讀；資料為鼎新 e-Go 匯出的歷史，不可修改</span></header>"
        f"<main>{body}</main>")


def columns(table: str):
    return query("""
        SELECT a.attname AS name, col_description(a.attrelid, a.attnum) AS zh
        FROM pg_attribute a
        WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum""", (f"ch001.{table}",))


@app.get("/", response_class=HTMLResponse)
def index(_: str = Depends(auth)):
    rows = query("""
        SELECT c.relname AS t, obj_description(c.oid) AS zh,
               c.reltuples::bigint AS n
        FROM pg_class c
        WHERE c.relnamespace = 'ch001'::regnamespace AND c.relkind = 'r'
        ORDER BY c.relname""")
    groups: dict[str, list] = {}
    for r in rows:
        desc = r["zh"] or ""
        m = re.search(r"〔(.+?)〕", desc)
        mod = m.group(1) if m else "其他"
        groups.setdefault(mod, []).append(r)
    body = ["<p class=note>點表名進去看資料。欄位標題的中文是從舊系統的畫面標籤、"
            "資料字典與資料本身推出來的，標著<span class=undef>（語意未定）</span>"
            "的就是還沒認出來的欄位 —— 認得出來請告訴我們。</p>"]
    for mod, items in sorted(groups.items()):
        body.append(f"<h2>{escape(mod)}</h2><div class=grid>")
        for r in items:
            name = table_label(r["zh"] or "", r["t"])
            cnt = query(f'SELECT count(*) c FROM ch001."{ident(r["t"])}"')[0]["c"]
            body.append(
                f"<div class=card><a href='/t/{r['t']}'>{escape(name)}</a>"
                f"<div class=n>{escape(r['t'])}　{cnt:,} 列</div></div>")
        body.append("</div>")
    return page("表清單", "".join(body))


@app.get("/t/{table}", response_class=HTMLResponse)
def browse(table: str, q: str = Query("", max_length=80), page_no: int = Query(1, ge=1),
           _: str = Depends(auth)):
    table = ident(table)
    cols = columns(table)
    if not cols:
        raise HTTPException(404, "查無此表")
    names = [c["name"] for c in cols]
    where, args = "", []
    if q:
        # 全欄位模糊比對：欄位名是白名單來的，值走參數化
        cond = " OR ".join(f'"{n}"::text ILIKE %s' for n in names)
        where = f"WHERE {cond}"
        args = [f"%{q}%"] * len(names)
    total = query(f'SELECT count(*) c FROM ch001."{table}" {where}', args)[0]["c"]
    off = (page_no - 1) * PAGE_SIZE
    rows = query(f'SELECT * FROM ch001."{table}" {where} '
                 f'ORDER BY 1 LIMIT {PAGE_SIZE} OFFSET %s', args + [off])
    desc = query("SELECT obj_description(%s::regclass) d", (f"ch001.{table}",))[0]["d"] or table

    head = "".join(th(c) for c in cols)
    drill = DETAILS.get(table)
    trs = []
    for r in rows:
        tds = []
        keyval = KEY_SEP.join(str(r[k] or "") for k in HEAD_KEYS.get(table, ()))
        for i, n in enumerate(names):
            v = "" if r[n] is None else str(r[n])
            if i == 0 and drill:
                tds.append(f"<td><a href='/t/{table}/{escape(keyval)}'>{escape(v)}</a></td>")
            else:
                tds.append(f"<td title='{escape(v)}'>{escape(v)}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")

    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    qs = f"&q={escape(q)}" if q else ""
    prev = f"/t/{table}?page_no={page_no-1}{qs}" if page_no > 1 else "#"
    nxt = f"/t/{table}?page_no={page_no+1}{qs}" if page_no < pages else "#"
    body = f"""
      <h2>{escape(desc)}</h2>
      <form class=bar method=get>
        <input type=search name=q value="{escape(q)}" placeholder="搜尋任一欄位（單號、名稱、金額…）">
        <button>搜尋</button>
        {'<a class=btn href="/t/' + table + '">清除</a>' if q else ''}
        <span class=n>共 {total:,} 列　第 {page_no}／{max(pages,1)} 頁</span>
        <a class=btn href="{prev}" {'aria-disabled=true' if page_no<=1 else ''}>上一頁</a>
        <a class=btn href="{nxt}" {'aria-disabled=true' if page_no>=pages else ''}>下一頁</a>
      </form>
      <div class=wrap><table><thead><tr>{head}</tr></thead><tbody>{''.join(trs)}</tbody></table></div>"""
    return page(desc, body)


@app.get("/t/{table}/{key}", response_class=HTMLResponse)
def detail(table: str, key: str, _: str = Depends(auth)):
    table = ident(table)
    cols = columns(table)
    if not cols:
        raise HTTPException(404, "查無此表")
    keycols = HEAD_KEYS.get(table) or (cols[0]["name"],)
    vals = key.split(KEY_SEP)
    if len(vals) != len(keycols):
        raise HTTPException(400, "鍵值數量不符")
    cond = " AND ".join(f'"{ident(k)}" = %s' for k in keycols)
    head_rows = query(f'SELECT * FROM ch001."{table}" WHERE {cond} LIMIT 1', tuple(vals))
    if not head_rows:
        raise HTTPException(404, "查無此筆")
    r = head_rows[0]
    desc = query("SELECT obj_description(%s::regclass) d", (f"ch001.{table}",))[0]["d"] or table
    title = desc.split("　")[0]
    items = []
    for c in cols:
        v = r[c["name"]]
        if v is None or str(v) == "":
            continue
        items.append(f"<tr>{th(c)}<td>{escape(str(v))}</td></tr>")
    body = [f"<h2>{escape(title)}　{escape(key.replace(KEY_SEP, ' / '))}</h2>",
            "<div class='wrap fit'><table class=kv>" + "".join(items) + "</table></div>"]

    drill = DETAILS.get(table)
    if drill:
        dt, hk, dk = drill
        args = tuple(r[k] for k in hk)
        cond = " AND ".join(f'"{ident(k)}" = %s' for k in dk)
        dcols = columns(dt)
        drows = query(f'SELECT * FROM ch001."{dt}" WHERE {cond} ORDER BY 1', args)
        if drows:
            dhead = "".join(th(c) for c in dcols)
            dtrs = "".join("<tr>" + "".join(
                f"<td>{escape('' if row[c['name']] is None else str(row[c['name']]))}</td>"
                for c in dcols) + "</tr>" for row in drows)
            dd = query("SELECT obj_description(%s::regclass) d", (f"ch001.{dt}",))[0]["d"] or dt
            body.append(f"<h2>{escape(dd.split('　')[0])}　{len(drows)} 筆</h2>"
                        f"<div class=wrap><table><thead><tr>{dhead}</tr></thead>"
                        f"<tbody>{dtrs}</tbody></table></div>")
    return page(f"{title} {key}", "".join(body))


@app.get("/healthz")
def healthz():
    return {"ok": True, "tables": query(
        "SELECT count(*) c FROM pg_class WHERE relnamespace='ch001'::regnamespace "
        "AND relkind='r'")[0]["c"]}
