"""ctos CLI 主程式

用法總覽：
  ctos login                          登入並換發長效 API token
  ctos logout                         清除本機 token
  ctos whoami                         顯示目前身份
  ctos token list / revoke <id>      管理 API token（需重新輸入帳密）
  ctos kb get <kb-id>                 讀取知識庫條目
  ctos kb search <關鍵字>             全文搜尋知識庫
  ctos kb attachments <kb-id>         列出 / 下載附件
  ctos lib ls [路徑]                  瀏覽圖書館
  ctos lib get <路徑>                 下載圖書館檔案
"""

import argparse
import getpass
import json
import os
import socket
import sys
from pathlib import Path

from . import __version__
from .api import ApiError, request
from .config import get_token, get_url, load_config, save_config

LIBRARY_ROOT = "library"


def _die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _require_url() -> str:
    url = get_url()
    if not url:
        _die("尚未設定服務網址，請先執行：ctos login --url <網址>")
    return url


def _require_token() -> str:
    token = get_token()
    if not token:
        _die("尚未登入，請先執行：ctos login")
    return token


def _api(path: str, **kwargs):
    """帶 token 的 API 請求，401/403 時給出可行動的指引"""
    url = _require_url()
    token = _require_token()
    try:
        return request(url, path, token=token, **kwargs)
    except ApiError as e:
        if e.status == 401:
            _die("token 無效或已過期，請重新執行：ctos login")
        if e.status == 403 and "唯讀" in e.detail:
            _die(
                f"API 錯誤（HTTP 403）：{e.detail}\n"
                "目前的 token 是唯讀的。要使用寫入指令，請重新換發可寫 token：\n"
                "  ctos login --read-write"
            )
        if e.status == 403 and "全域知識" in e.detail:
            _die(
                f"API 錯誤（HTTP 403）：{e.detail}\n"
                "建立 global 知識需要 global_write 權限（請管理者在後台開），\n"
                "或改用 --scope personal / --scope project。"
            )
        _die(f"API 錯誤（HTTP {e.status}）：{e.detail}")


def _session_login(url: str, username: str | None = None) -> tuple[str, str]:
    """登入並回傳 (session_token, username)

    帳號優先序：參數（--username）> 互動輸入
    密碼優先序：環境變數 CTOS_PASSWORD > 互動輸入（getpass）
    沒有互動式終端機（如 CI、Claude Code 的 ! 指令）時給出明確指引。
    """
    try:
        if not username:
            username = input("帳號：").strip()
        password = os.environ.get("CTOS_PASSWORD") or getpass.getpass("密碼：")
    except EOFError:
        _die(
            "無法互動輸入帳密（目前環境沒有終端機輸入）。\n"
            "請改在一般終端機執行，或改用非互動方式：\n"
            "  CTOS_PASSWORD=<密碼> ctos login --username <帳號> [--url <網址>]"
        )
    if not username:
        _die("未提供帳號")
    resp = request(
        url,
        "/api/auth/login",
        method="POST",
        json_body={"username": username, "password": password},
    )
    if not resp.get("success"):
        _die(f"登入失敗：{resp.get('error', '帳號或密碼錯誤')}")
    if resp.get("must_change_password"):
        print("注意：此帳號被要求變更密碼，請先到 web 介面變更後再使用 CLI。")
    return resp["token"], username


def _session_logout(url: str, session_token: str) -> None:
    try:
        request(url, "/api/auth/logout", method="POST", token=session_token)
    except ApiError:
        pass  # 登出失敗不影響流程


# ============================================================
# auth 子命令
# ============================================================


def cmd_login(args: argparse.Namespace) -> None:
    cfg = load_config()
    url = args.url or get_url(cfg)
    if not url:
        try:
            url = input("服務網址（如 https://ching-tech.ddns.net/ctos）：")
        except EOFError:
            _die("未提供服務網址，請加 --url <網址>")
    url = url.strip().rstrip("/")
    if not url:
        _die("未提供服務網址")

    session_token, username = _session_login(url, username=args.username)

    default_name = f"{getpass.getuser()}@{socket.gethostname()}"
    name = args.name or default_name
    try:
        resp = request(
            url,
            "/api/auth/tokens",
            method="POST",
            token=session_token,
            json_body={
                "name": name,
                "scopes": args.scope or ["knowledge-base"],
                "expires_days": args.expires_days,
                "read_only": not args.read_write,
            },
        )
    except ApiError as e:
        _session_logout(url, session_token)
        _die(f"換發 API token 失敗（HTTP {e.status}）：{e.detail}")
    finally:
        _session_logout(url, session_token)

    pat = resp["token"]
    info = resp.get("info", {})
    save_config(
        {
            "url": url,
            "token": pat,
            "username": username,
            "token_name": info.get("name", name),
            "token_id": info.get("id"),
        }
    )
    expires = info.get("expires_at") or "永不過期"
    print(f"登入成功：{username}")
    print(f"已換發 API token「{info.get('name', name)}」並存入設定檔（效期至 {expires}）")
    print("之後可直接使用 ctos kb / ctos lib 等指令。")


def cmd_logout(_args: argparse.Namespace) -> None:
    cfg = load_config()
    if not cfg.get("token"):
        print("本機沒有已儲存的 token。")
        return
    token_id = cfg.get("token_id")
    cfg.pop("token", None)
    save_config(cfg)
    print("已清除本機 token。")
    if token_id is not None:
        print(f"注意：伺服器端 token（id={token_id}）仍有效，要撤銷請執行：ctos token revoke {token_id}")


def cmd_whoami(_args: argparse.Namespace) -> None:
    me = _api("/api/user/me")
    cfg = load_config()
    print(f"帳號：{me.get('username', cfg.get('username', '?'))}")
    if me.get("display_name"):
        print(f"名稱：{me['display_name']}")

    role = me.get("role")
    account_role = me.get("account_role")
    if role:
        if me.get("auth_type") == "pat" and account_role and account_role != role:
            # PAT 一律降權為 user，與帳號實際角色不同時標明，避免誤判帳號權限
            print(f"角色：{role}（API token 降權；帳號實際角色：{account_role}）")
        else:
            print(f"角色：{role}")

    print(f"服務：{get_url() or '?'}")
    if cfg.get("token_name"):
        print(f"token：{cfg['token_name']}（id={cfg.get('token_id', '?')}）")


def cmd_token_list(_args: argparse.Namespace) -> None:
    url = _require_url()
    print("管理 API token 需要帳號密碼登入。")
    session_token, _ = _session_login(url)
    try:
        resp = request(url, "/api/auth/tokens", token=session_token)
        tokens = resp.get("tokens", [])
        if not tokens:
            print("沒有任何 API token。")
            return
        print(f"{'id':>4}  {'名稱':<30} {'唯讀':<4} {'效期':<22} 最後使用")
        for t in tokens:
            ro = "是" if t.get("read_only") else "否"
            print(
                f"{t['id']:>4}  {t['name']:<30} {ro:<4} "
                f"{(t.get('expires_at') or '永久'):<22} {t.get('last_used_at') or '-'}"
            )
    finally:
        _session_logout(url, session_token)


def cmd_token_revoke(args: argparse.Namespace) -> None:
    url = _require_url()
    print("管理 API token 需要帳號密碼登入。")
    session_token, _ = _session_login(url)
    try:
        request(
            url,
            f"/api/auth/tokens/{args.token_id}",
            method="DELETE",
            token=session_token,
        )
        print(f"已撤銷 token id={args.token_id}")
    except ApiError as e:
        _die(f"撤銷失敗（HTTP {e.status}）：{e.detail}")
    finally:
        _session_logout(url, session_token)


# ============================================================
# kb 子命令
# ============================================================


def _attachment_api_path(att_path: str) -> str | None:
    """把知識附件的儲存路徑轉成 API 路徑"""
    for prefix in ("local://knowledge/", "ctos://knowledge/", "nas://knowledge/"):
        if att_path.startswith(prefix):
            return "/api/knowledge/" + att_path[len(prefix):]
    if att_path.startswith("../assets/"):
        return "/api/knowledge/assets/" + att_path[len("../assets/"):]
    return None


def cmd_kb_get(args: argparse.Namespace) -> None:
    kb = _api(f"/api/knowledge/{args.kb_id}")
    if args.json:
        print(json.dumps(kb, ensure_ascii=False, indent=2))
        return
    if args.content_only:
        print(kb.get("content", ""))
        return

    tags = kb.get("tags") or {}
    print(f"# {kb['id']}: {kb['title']}")
    print(
        f"類型 {kb.get('type')} / 分類 {kb.get('category')} / 範圍 {kb.get('scope')}"
        + (f"（owner: {kb['owner']}）" if kb.get("owner") else "")
    )
    if tags.get("topics"):
        print(f"主題：{', '.join(tags['topics'])}")
    print(f"作者 {kb.get('author')}；建立 {kb.get('created_at')}；更新 {kb.get('updated_at')}")
    attachments = kb.get("attachments") or []
    if attachments:
        print(f"附件 {len(attachments)} 個（ctos kb attachments {kb['id']} 查看）")
    print("-" * 60)
    print(kb.get("content", ""))


def cmd_kb_search(args: argparse.Namespace) -> None:
    params = {
        "q": args.query,
        "scope": args.scope,
        "type": args.type,
        "category": args.category,
        "project": args.project,
        "topics": args.topic or None,
    }
    resp = _api("/api/knowledge", params=params)
    if args.json:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return
    items = resp.get("items", [])
    if not items:
        print("沒有符合的知識條目。")
        return
    print(f"共 {resp.get('total', len(items))} 筆：")
    for item in items:
        scope = item.get("scope", "global")
        owner = f"/{item['owner']}" if item.get("owner") else ""
        print(f"  {item['id']:<8} [{scope}{owner}] {item['title']}")
        if item.get("snippet"):
            snippet = item["snippet"].replace("\n", " ").strip()
            print(f"           {snippet[:100]}")


def _read_content_arg(args: argparse.Namespace) -> str | None:
    """從 --content / --file 取得內容；--file - 代表讀 stdin

    刻意不自動吃 stdin：非互動環境（Claude / CI）誤觸會把內容設成空字串。
    """
    if args.content is not None and args.file is not None:
        _die("--content 與 --file 只能擇一")
    if args.content is not None:
        return args.content
    if args.file is not None:
        if args.file == "-":
            return sys.stdin.read()
        file_path = Path(args.file)
        if not file_path.exists():
            _die(f"找不到檔案：{args.file}")
        return file_path.read_text(encoding="utf-8")
    return None


def _build_tags(args: argparse.Namespace) -> dict | None:
    """從 --topic / --role / --level 組 tags，全部未提供時回 None"""
    if not (args.topic or args.role or args.level):
        return None
    return {
        "projects": [],
        "roles": args.role or [],
        "topics": args.topic or [],
        "level": args.level,
    }


def cmd_kb_add(args: argparse.Namespace) -> None:
    content = _read_content_arg(args)
    if content is None:
        _die("請以 --content <文字> 或 --file <路徑>（--file - 讀 stdin）提供內容")
    if not args.title.strip():
        _die("--title 不可為空")
    if args.scope == "project" and not args.project_id:
        _die("--scope project 需要一併提供 --project-id")

    cfg = load_config()
    body = {
        "title": args.title.strip(),
        "content": content,
        "scope": args.scope,
        "type": args.type,
        "category": args.category,
        "is_public": args.public,
        "author": cfg.get("username") or "ctos-cli",
    }
    if args.project_id:
        body["project_id"] = args.project_id
    tags = _build_tags(args)
    if tags:
        body["tags"] = tags

    kb = _api("/api/knowledge", method="POST", json_body=body)
    if args.json:
        print(json.dumps(kb, ensure_ascii=False, indent=2))
        return
    owner = f"（owner: {kb['owner']}）" if kb.get("owner") else ""
    print(f"已建立 {kb['id']}: {kb['title']}")
    print(f"範圍 {kb.get('scope')}{owner}")
    if kb.get("scope") == "personal":
        print("提醒：personal 條目只有你自己查得到，團隊要共用請用 --scope global 或 project。")


def cmd_kb_update(args: argparse.Namespace) -> None:
    content = _read_content_arg(args)

    body: dict = {}
    if args.title is not None:
        body["title"] = args.title
    if content is not None:
        body["content"] = content
    if args.scope is not None:
        body["scope"] = args.scope
    if args.type is not None:
        body["type"] = args.type
    if args.category is not None:
        body["category"] = args.category
    if args.public is not None:
        body["is_public"] = args.public

    tags = _build_tags(args)
    if tags:
        # tags 是整包取代：先讀現況合併，避免清掉沒指定的維度
        current = _api(f"/api/knowledge/{args.kb_id}")
        current_tags = current.get("tags") or {}
        body["tags"] = {
            "projects": current_tags.get("projects", []),
            "roles": args.role or current_tags.get("roles", []),
            "topics": args.topic or current_tags.get("topics", []),
            "level": args.level if args.level is not None else current_tags.get("level"),
        }

    if not body:
        _die("沒有提供任何要更新的欄位")

    kb = _api(f"/api/knowledge/{args.kb_id}", method="PUT", json_body=body)
    if args.json:
        print(json.dumps(kb, ensure_ascii=False, indent=2))
        return
    print(f"已更新 {kb['id']}: {kb['title']}（範圍 {kb.get('scope')}）")


def cmd_kb_attachments(args: argparse.Namespace) -> None:
    kb = _api(f"/api/knowledge/{args.kb_id}")
    attachments = kb.get("attachments") or []
    if not attachments:
        print("此條目沒有附件。")
        return

    if not args.download:
        for i, att in enumerate(attachments):
            size = f"（{att['size']}）" if att.get("size") else ""
            print(f"  [{i}] {att.get('type', 'file')}: {att['path']}{size}")
        print(f"下載：ctos kb attachments {args.kb_id} --download [目錄]")
        return

    out_dir = Path(args.download if args.download is not True else ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    for att in attachments:
        api_path = _attachment_api_path(att["path"])
        if api_path is None:
            print(f"略過（無法辨識路徑格式）：{att['path']}")
            continue
        filename = att["path"].split("/")[-1]
        target = out_dir / filename
        content = _api(api_path, raw=True)
        target.write_bytes(content)
        print(f"已下載：{target}（{len(content)} bytes）")


# ============================================================
# lib 子命令
# ============================================================


def cmd_lib_ls(args: argparse.Namespace) -> None:
    sub = (args.path or "").strip("/")
    full = f"{LIBRARY_ROOT}/{sub}" if sub else LIBRARY_ROOT
    resp = _api(f"/api/files/shared/{full}/list")
    if args.json:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return
    if not resp.get("dirs") and not resp.get("files"):
        print("（空目錄）")
        return
    for d in resp.get("dirs", []):
        print(f"  {d}/")
    for f in resp.get("files", []):
        size_kb = f["size"] / 1024
        print(f"  {f['name']}  ({size_kb:.1f} KB)")


def cmd_lib_get(args: argparse.Namespace) -> None:
    sub = args.path.strip("/")
    content = _api(f"/api/files/shared/{LIBRARY_ROOT}/{sub}", raw=True)
    filename = sub.split("/")[-1]
    out = Path(args.out) if args.out else Path(filename)
    if out.is_dir():
        out = out / filename
    out.write_bytes(content)
    print(f"已下載：{out}（{len(content)} bytes）")


# ============================================================
# argparse
# ============================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctos",
        description="ching-tech-os 知識庫 / 圖書館遠端存取 CLI",
    )
    parser.add_argument("--version", action="version", version=f"ctos {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="登入並換發長效 API token")
    p_login.add_argument("--url", help="服務網址（如 https://ching-tech.ddns.net/ctos）")
    p_login.add_argument("--username", help="帳號（非互動環境用，密碼走環境變數 CTOS_PASSWORD）")
    p_login.add_argument("--name", help="token 名稱（預設 使用者@主機名）")
    p_login.add_argument("--expires-days", type=int, default=180, help="token 效期天數（預設 180）")
    p_login.add_argument("--scope", action="append", help="token scope（可重複，預設 knowledge-base）")
    p_login.add_argument("--read-write", action="store_true", help="允許寫入（預設唯讀）")
    p_login.set_defaults(func=cmd_login)

    sub.add_parser("logout", help="清除本機 token").set_defaults(func=cmd_logout)
    sub.add_parser("whoami", help="顯示目前身份").set_defaults(func=cmd_whoami)

    p_token = sub.add_parser("token", help="管理 API token")
    token_sub = p_token.add_subparsers(dest="token_command", required=True)
    token_sub.add_parser("list", help="列出 API token").set_defaults(func=cmd_token_list)
    p_revoke = token_sub.add_parser("revoke", help="撤銷 API token")
    p_revoke.add_argument("token_id", type=int)
    p_revoke.set_defaults(func=cmd_token_revoke)

    p_kb = sub.add_parser("kb", help="知識庫")
    kb_sub = p_kb.add_subparsers(dest="kb_command", required=True)

    p_get = kb_sub.add_parser("get", help="讀取知識條目")
    p_get.add_argument("kb_id", help="知識 ID（如 kb-182）")
    p_get.add_argument("--json", action="store_true", help="輸出完整 JSON")
    p_get.add_argument("--content-only", action="store_true", help="只輸出 Markdown 內容")
    p_get.set_defaults(func=cmd_kb_get)

    p_search = kb_sub.add_parser("search", help="全文搜尋")
    p_search.add_argument("query", help="關鍵字（空白分隔 = AND）")
    p_search.add_argument("--scope", help="global / personal / project")
    p_search.add_argument("--type", help="knowledge / context / operations / reference")
    p_search.add_argument("--category", help="technical / business / management")
    p_search.add_argument("--project", help="專案過濾")
    p_search.add_argument("--topic", action="append", help="主題過濾（可重複）")
    p_search.add_argument("--json", action="store_true")
    p_search.set_defaults(func=cmd_kb_search)

    p_add = kb_sub.add_parser("add", help="新增知識條目（需可寫 token：ctos login --read-write）")
    p_add.add_argument("--title", required=True, help="標題")
    p_add.add_argument("--content", help="內容（Markdown）")
    p_add.add_argument("--file", help="從檔案讀內容；- 代表 stdin")
    p_add.add_argument("--scope", default="personal", choices=["personal", "global", "project"], help="範圍（預設 personal；global 需 global_write 權限）")
    p_add.add_argument("--project-id", help="專案 UUID（--scope project 時必填）")
    p_add.add_argument("--type", default="note", help="類型（note/knowledge/reference 等，預設 note）")
    p_add.add_argument("--category", default="technical", help="分類（technical/business/management，預設 technical）")
    p_add.add_argument("--topic", action="append", help="主題標籤（可重複）")
    p_add.add_argument("--role", action="append", help="角色標籤（可重複）")
    p_add.add_argument("--level", help="層級（beginner/intermediate/advanced）")
    p_add.add_argument("--public", action="store_true", help="允許未綁定用戶查詢（限 global）")
    p_add.add_argument("--json", action="store_true")
    p_add.set_defaults(func=cmd_kb_add)

    p_upd = kb_sub.add_parser("update", help="更新知識條目（需可寫 token）")
    p_upd.add_argument("kb_id", help="知識 ID（如 kb-182）")
    p_upd.add_argument("--title", help="新標題")
    p_upd.add_argument("--content", help="新內容（整篇取代）")
    p_upd.add_argument("--file", help="從檔案讀新內容；- 代表 stdin")
    p_upd.add_argument("--scope", choices=["personal", "global", "project"], help="變更範圍")
    p_upd.add_argument("--type", help="變更類型")
    p_upd.add_argument("--category", help="變更分類")
    p_upd.add_argument("--topic", action="append", help="主題標籤（提供即整組取代主題，其他標籤維度保留）")
    p_upd.add_argument("--role", action="append", help="角色標籤")
    p_upd.add_argument("--level", help="層級")
    p_upd.add_argument("--public", action=argparse.BooleanOptionalAction, default=None, help="--public / --no-public")
    p_upd.add_argument("--json", action="store_true")
    p_upd.set_defaults(func=cmd_kb_update)

    p_att = kb_sub.add_parser("attachments", help="列出 / 下載附件")
    p_att.add_argument("kb_id")
    p_att.add_argument(
        "--download",
        nargs="?",
        const=True,
        default=None,
        metavar="目錄",
        help="下載全部附件到指定目錄（預設目前目錄）",
    )
    p_att.set_defaults(func=cmd_kb_attachments)

    p_lib = sub.add_parser("lib", help="圖書館")
    lib_sub = p_lib.add_subparsers(dest="lib_command", required=True)

    p_ls = lib_sub.add_parser("ls", help="瀏覽圖書館目錄")
    p_ls.add_argument("path", nargs="?", default="", help="子路徑（如 技術文件）")
    p_ls.add_argument("--json", action="store_true")
    p_ls.set_defaults(func=cmd_lib_ls)

    p_lget = lib_sub.add_parser("get", help="下載圖書館檔案")
    p_lget.add_argument("path", help="檔案路徑（如 技術文件/規格書.pdf）")
    p_lget.add_argument("--out", help="輸出檔名或目錄")
    p_lget.set_defaults(func=cmd_lib_get)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
