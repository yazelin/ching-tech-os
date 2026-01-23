#!/usr/bin/env python3
"""
從舊系統遷移資料到 chingtech 租戶

使用方式:
    cd /home/ct/SDD/ching-tech-os/backend
    uv run python ../scripts/migrate_from_old_system.py
"""

import asyncio
import subprocess
import json
from pathlib import Path
from datetime import datetime

import asyncpg

# 設定
OLD_SYSTEM_HOST = "192.168.11.11"
OLD_SYSTEM_USER = "ct"
OLD_SYSTEM_PASSWORD = "36274806"

NEW_DB_HOST = "localhost"
NEW_DB_PORT = 5432
NEW_DB_USER = "ching_tech"
NEW_DB_PASSWORD = "ching_tech_dev"
NEW_DB_NAME = "ching_tech_os"

# chingtech 租戶 ID
TENANT_ID = "fe530f72-f9f5-434c-ba0b-8bc2d6485ca3"

# NAS 路徑
OLD_NAS_BASE = "/mnt/nas/ctos"
NEW_TENANT_BASE = f"/mnt/nas/ctos/tenants/{TENANT_ID}"


def run_remote_psql(query: str) -> str:
    """在舊系統執行 SQL 查詢（返回分隔格式）"""
    cmd = [
        "sshpass", "-p", OLD_SYSTEM_PASSWORD,
        "ssh", f"{OLD_SYSTEM_USER}@{OLD_SYSTEM_HOST}",
        f'docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -t -A -F "|||" -c "{query}"'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing query: {result.stderr}")
        return ""
    return result.stdout.strip()


def run_remote_psql_json(query: str) -> list[dict]:
    """在舊系統執行 SQL 查詢並返回 JSON"""
    # 使用 row_to_json 來確保正確處理特殊字元
    json_query = f"SELECT json_agg(row_to_json(t)) FROM ({query}) t"
    cmd = [
        "sshpass", "-p", OLD_SYSTEM_PASSWORD,
        "ssh", f"{OLD_SYSTEM_USER}@{OLD_SYSTEM_HOST}",
        f'docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -t -A -c "{json_query}"'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing query: {result.stderr}")
        return []

    output = result.stdout.strip()
    if not output or output == 'null':
        return []

    try:
        return json.loads(output) or []
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return []


def parse_timestamp(value: str | None) -> datetime | None:
    """解析時間戳記字串"""
    if not value:
        return None
    try:
        import re
        # 移除時區部分
        # 處理 ISO 格式: 2025-01-07T02:00:00+00:00 或 2026-01-21 08:26:05.438454+00
        value = re.sub(r'[+-]\d{2}:\d{2}$', '', value.strip())  # +00:00 格式
        value = re.sub(r'[+-]\d{2}$', '', value.strip())         # +00 格式

        # 將 T 分隔符替換為空格
        value = value.replace('T', ' ')

        # 嘗試多種格式
        for fmt in [
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
    except Exception as e:
        print(f"Warning: failed to parse timestamp '{value}': {e}")
        return None


def parse_date(value: str | None):
    """解析日期字串"""
    from datetime import date
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def parse_row(line: str, columns: list[str]) -> dict | None:
    """解析資料行"""
    if not line.strip():
        return None
    parts = line.split("|||")
    if len(parts) != len(columns):
        print(f"Warning: column count mismatch. Expected {len(columns)}, got {len(parts)}")
        return None
    row = {}
    for i, col in enumerate(columns):
        value = parts[i] if parts[i] else None
        row[col] = value
    return row


async def migrate_projects(conn):
    """遷移專案資料"""
    print("\n=== 遷移專案 ===")

    query = "SELECT id, name, description, status, start_date, end_date, created_at, updated_at, created_by FROM projects"
    rows = run_remote_psql_json(query)

    if not rows:
        print("沒有專案資料")
        return {}

    project_map = {}  # old_id -> new_id

    for row in rows:
        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM projects WHERE name = $1 AND tenant_id = $2",
            row["name"], TENANT_ID
        )

        if existing:
            print(f"  跳過已存在的專案: {row['name']}")
            project_map[row["id"]] = str(existing["id"])
            continue

        # 插入新專案
        created_at = parse_timestamp(row.get("created_at")) or datetime.now()
        updated_at = parse_timestamp(row.get("updated_at")) or datetime.now()

        new_id = await conn.fetchval("""
            INSERT INTO projects (name, description, status, start_date, end_date, created_at, updated_at, created_by, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """, row["name"], row.get("description"), row.get("status"),
            parse_date(row.get("start_date")), parse_date(row.get("end_date")),
            created_at, updated_at, row.get("created_by"), TENANT_ID)

        project_map[row["id"]] = str(new_id)
        print(f"  已遷移專案: {row['name']}")

    return project_map


async def migrate_vendors(conn):
    """遷移廠商資料"""
    print("\n=== 遷移廠商 ===")

    query = "SELECT id, name, erp_code, short_name, contact_person, phone, fax, email, address, tax_id, payment_terms, notes, is_active, created_at, updated_at FROM vendors"
    data = run_remote_psql(query)

    if not data:
        print("沒有廠商資料")
        return {}

    columns = ["id", "name", "erp_code", "short_name", "contact_person", "phone", "fax", "email", "address", "tax_id", "payment_terms", "notes", "is_active", "created_at", "updated_at"]
    vendor_map = {}

    for line in data.split("\n"):
        row = parse_row(line, columns)
        if not row:
            continue

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM vendors WHERE name = $1 AND tenant_id = $2",
            row["name"], TENANT_ID
        )

        if existing:
            print(f"  跳過已存在的廠商: {row['name']}")
            vendor_map[row["id"]] = str(existing["id"])
            continue

        created_at = parse_timestamp(row["created_at"]) or datetime.now()
        updated_at = parse_timestamp(row["updated_at"]) or datetime.now()

        new_id = await conn.fetchval("""
            INSERT INTO vendors (name, erp_code, short_name, contact_person, phone, fax, email, address, tax_id, payment_terms, notes, is_active, created_at, updated_at, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            RETURNING id
        """, row["name"], row["erp_code"], row["short_name"], row["contact_person"],
            row["phone"], row["fax"], row["email"], row["address"], row["tax_id"],
            row["payment_terms"], row["notes"], row["is_active"] == "t" if row["is_active"] else True,
            created_at, updated_at, TENANT_ID)

        vendor_map[row["id"]] = str(new_id)
        print(f"  已遷移廠商: {row['name']}")

    return vendor_map


async def migrate_users(conn):
    """遷移使用者資料"""
    print("\n=== 遷移使用者 ===")

    query = "SELECT id, username, display_name, preferences, created_at, last_login_at FROM users"
    data = run_remote_psql(query)

    if not data:
        print("沒有使用者資料")
        return {}

    columns = ["id", "username", "display_name", "preferences", "created_at", "last_login_at"]
    user_map = {}  # old_id -> new_id

    for line in data.split("\n"):
        row = parse_row(line, columns)
        if not row:
            continue

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1 AND tenant_id = $2",
            row["username"], TENANT_ID
        )

        if existing:
            print(f"  跳過已存在的使用者: {row['username']}")
            user_map[row["id"]] = str(existing["id"])
            continue

        # 插入新使用者（新系統使用 NAS 登入，不需要密碼）
        new_id = await conn.fetchval("""
            INSERT INTO users (username, display_name, preferences, created_at, last_login_at, tenant_id, role, is_active)
            VALUES ($1, $2, $3::jsonb, $4, $5, $6, 'user', true)
            RETURNING id
        """, row["username"], row["display_name"], row["preferences"] or "{}",
            parse_timestamp(row["created_at"]), parse_timestamp(row["last_login_at"]), TENANT_ID)

        user_map[row["id"]] = str(new_id)
        print(f"  已遷移使用者: {row['username']}")

    return user_map


async def migrate_project_members(conn, project_map: dict, user_map: dict):
    """遷移專案成員"""
    print("\n=== 遷移專案成員 ===")

    query = "SELECT id, project_id, user_id, name, role, company, email, phone, notes, is_internal, created_at FROM project_members"
    data = run_remote_psql(query)

    if not data:
        print("沒有專案成員資料")
        return

    columns = ["id", "project_id", "user_id", "name", "role", "company", "email", "phone", "notes", "is_internal", "created_at"]

    for line in data.split("\n"):
        row = parse_row(line, columns)
        if not row:
            continue

        new_project_id = project_map.get(row["project_id"])
        if not new_project_id:
            print(f"  跳過成員 {row['name']}：找不到對應專案")
            continue

        new_user_id = user_map.get(row["user_id"]) if row["user_id"] else None

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM project_members WHERE project_id = $1 AND name = $2",
            new_project_id, row["name"]
        )

        if existing:
            print(f"  跳過已存在的成員: {row['name']}")
            continue

        await conn.execute("""
            INSERT INTO project_members (project_id, user_id, name, role, company, email, phone, notes, is_internal, created_at, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, new_project_id, int(new_user_id) if new_user_id else None,
            row["name"], row["role"], row["company"], row["email"], row["phone"],
            row["notes"], row["is_internal"] == "t" if row["is_internal"] else True,
            parse_timestamp(row["created_at"]), TENANT_ID)

        print(f"  已遷移成員: {row['name']}")


async def migrate_project_milestones(conn, project_map: dict):
    """遷移專案里程碑"""
    print("\n=== 遷移專案里程碑 ===")

    query = "SELECT id, project_id, name, milestone_type, planned_date, actual_date, status, notes, created_at, updated_at FROM project_milestones"
    rows = run_remote_psql_json(query)

    if not rows:
        print("沒有里程碑資料")
        return

    for row in rows:
        new_project_id = project_map.get(row["project_id"])
        if not new_project_id:
            print(f"  跳過里程碑 {row['name']}：找不到對應專案")
            continue

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM project_milestones WHERE project_id = $1 AND name = $2",
            new_project_id, row["name"]
        )

        if existing:
            print(f"  跳過已存在的里程碑: {row['name']}")
            continue

        created_at = parse_timestamp(row.get("created_at")) or datetime.now()
        updated_at = parse_timestamp(row.get("updated_at")) or datetime.now()

        await conn.execute("""
            INSERT INTO project_milestones (project_id, name, milestone_type, planned_date, actual_date, status, notes, created_at, updated_at, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, new_project_id, row["name"], row.get("milestone_type"),
            parse_date(row.get("planned_date")), parse_date(row.get("actual_date")),
            row.get("status"), row.get("notes"), created_at, updated_at, TENANT_ID)

        print(f"  已遷移里程碑: {row['name']}")


async def migrate_project_meetings(conn, project_map: dict):
    """遷移專案會議"""
    print("\n=== 遷移專案會議 ===")

    query = "SELECT id, project_id, title, meeting_date, location, attendees, content, created_at, updated_at FROM project_meetings"
    rows = run_remote_psql_json(query)

    if not rows:
        print("沒有會議資料")
        return

    for row in rows:
        new_project_id = project_map.get(row["project_id"])
        if not new_project_id:
            print(f"  跳過會議 {row['title']}：找不到對應專案")
            continue

        meeting_date = parse_timestamp(row.get("meeting_date"))

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM project_meetings WHERE project_id = $1 AND title = $2 AND meeting_date = $3",
            new_project_id, row["title"], meeting_date
        )

        if existing:
            print(f"  跳過已存在的會議: {row['title']}")
            continue

        created_at = parse_timestamp(row.get("created_at")) or datetime.now()
        updated_at = parse_timestamp(row.get("updated_at")) or datetime.now()

        await conn.execute("""
            INSERT INTO project_meetings (project_id, title, meeting_date, location, attendees, content, created_at, updated_at, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, new_project_id, row["title"], meeting_date,
            row.get("location"), row.get("attendees"), row.get("content"),
            created_at, updated_at, TENANT_ID)

        print(f"  已遷移會議: {row['title']}")


async def migrate_project_attachments(conn, project_map: dict):
    """遷移專案附件"""
    print("\n=== 遷移專案附件 ===")

    # 注意：欄位名是 filename 不是 file_name，uploaded_at 不是 created_at
    query = "SELECT id, project_id, filename, file_type, file_size, storage_path, description, uploaded_at, uploaded_by FROM project_attachments"
    rows = run_remote_psql_json(query)

    if not rows:
        print("沒有附件資料")
        return

    for row in rows:
        new_project_id = project_map.get(row["project_id"])
        if not new_project_id:
            print(f"  跳過附件 {row['filename']}：找不到對應專案")
            continue

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM project_attachments WHERE project_id = $1 AND filename = $2 AND storage_path = $3",
            new_project_id, row["filename"], row.get("storage_path")
        )

        if existing:
            print(f"  跳過已存在的附件: {row['filename']}")
            continue

        uploaded_at = parse_timestamp(row.get("uploaded_at")) or datetime.now()

        # 路徑不需要轉換，path_manager 會根據 tenant_id 自動處理
        await conn.execute("""
            INSERT INTO project_attachments (project_id, filename, file_type, file_size, storage_path, description, uploaded_at, uploaded_by, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, new_project_id, row["filename"], row.get("file_type"),
            row.get("file_size"), row.get("storage_path"),
            row.get("description"), uploaded_at, row.get("uploaded_by"), TENANT_ID)

        print(f"  已遷移附件: {row['filename']}")


async def migrate_line_groups(conn, project_map: dict):
    """遷移 Line 群組"""
    print("\n=== 遷移 Line 群組 ===")

    query = "SELECT id, line_group_id, name, picture_url, member_count, project_id, is_active, joined_at, left_at, created_at, updated_at, allow_ai_response FROM line_groups"
    rows = run_remote_psql_json(query)

    if not rows:
        print("沒有 Line 群組資料")
        return {}

    group_map = {}

    for row in rows:
        new_project_id = project_map.get(row["project_id"]) if row.get("project_id") else None

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM line_groups WHERE line_group_id = $1",
            row["line_group_id"]
        )

        if existing:
            print(f"  跳過已存在的群組: {row['name']}")
            group_map[row["id"]] = str(existing["id"])
            continue

        created_at = parse_timestamp(row.get("created_at")) or datetime.now()
        updated_at = parse_timestamp(row.get("updated_at")) or datetime.now()

        new_id = await conn.fetchval("""
            INSERT INTO line_groups (line_group_id, name, picture_url, member_count, project_id, is_active, joined_at, left_at, created_at, updated_at, allow_ai_response, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        """, row["line_group_id"], row["name"], row.get("picture_url"),
            int(row["member_count"]) if row.get("member_count") else 0,
            new_project_id, row.get("is_active", True),
            parse_timestamp(row.get("joined_at")), parse_timestamp(row.get("left_at")),
            created_at, updated_at,
            row.get("allow_ai_response", False),
            TENANT_ID)

        group_map[row["id"]] = str(new_id)
        print(f"  已遷移群組: {row['name']}")

    return group_map


async def migrate_line_users(conn, user_map: dict):
    """遷移 Line 使用者"""
    print("\n=== 遷移 Line 使用者 ===")

    query = "SELECT id, line_user_id, display_name, picture_url, status_message, user_id, created_at, updated_at FROM line_users"
    rows = run_remote_psql_json(query)

    if not rows:
        print("沒有 Line 使用者資料")
        return {}

    line_user_map = {}

    for row in rows:
        new_user_id = user_map.get(str(row["user_id"])) if row.get("user_id") else None

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM line_users WHERE line_user_id = $1",
            row["line_user_id"]
        )

        if existing:
            print(f"  跳過已存在的 Line 使用者: {row['display_name']}")
            line_user_map[row["id"]] = str(existing["id"])
            continue

        created_at = parse_timestamp(row.get("created_at")) or datetime.now()
        updated_at = parse_timestamp(row.get("updated_at")) or datetime.now()

        new_id = await conn.fetchval("""
            INSERT INTO line_users (line_user_id, display_name, picture_url, status_message, user_id, created_at, updated_at, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, row["line_user_id"], row["display_name"], row.get("picture_url"),
            row.get("status_message"), int(new_user_id) if new_user_id else None,
            created_at, updated_at, TENANT_ID)

        line_user_map[row["id"]] = str(new_id)
        print(f"  已遷移 Line 使用者: {row['display_name']}")

    return line_user_map


async def migrate_inventory_items(conn, vendor_map: dict):
    """遷移庫存物料"""
    print("\n=== 遷移庫存物料 ===")

    # 新系統沒有 model 和 storage_location 欄位，把它們合併到 specification 和 notes
    query = "SELECT id, name, model, specification, unit, category, default_vendor, default_vendor_id, current_stock, min_stock, storage_location, notes, created_at, updated_at, created_by FROM inventory_items"
    rows = run_remote_psql_json(query)

    if not rows:
        print("沒有庫存資料")
        return {}

    item_map = {}

    for row in rows:
        new_vendor_id = vendor_map.get(str(row["default_vendor_id"])) if row.get("default_vendor_id") else None

        # 檢查是否已存在
        existing = await conn.fetchrow(
            "SELECT id FROM inventory_items WHERE name = $1 AND tenant_id = $2",
            row["name"], TENANT_ID
        )

        if existing:
            print(f"  跳過已存在的物料: {row['name']}")
            item_map[str(row["id"])] = str(existing["id"])
            continue

        created_at = parse_timestamp(row.get("created_at")) or datetime.now()
        updated_at = parse_timestamp(row.get("updated_at")) or datetime.now()

        # 將 model 併入 specification
        spec_parts = []
        if row.get("model"):
            spec_parts.append(f"型號: {row['model']}")
        if row.get("specification"):
            spec_parts.append(row["specification"])
        specification = "\n".join(spec_parts) if spec_parts else None

        # 將 storage_location 併入 notes
        notes_parts = []
        if row.get("storage_location"):
            notes_parts.append(f"儲位: {row['storage_location']}")
        if row.get("notes"):
            notes_parts.append(row["notes"])
        notes = "\n".join(notes_parts) if notes_parts else None

        new_id = await conn.fetchval("""
            INSERT INTO inventory_items (name, specification, unit, category, default_vendor, default_vendor_id, current_stock, min_stock, notes, created_at, updated_at, created_by, tenant_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING id
        """, row["name"], specification, row.get("unit"),
            row.get("category"), row.get("default_vendor"), new_vendor_id,
            float(row["current_stock"]) if row.get("current_stock") else 0,
            float(row["min_stock"]) if row.get("min_stock") else 0,
            notes, created_at, updated_at, row.get("created_by"), TENANT_ID)

        item_map[str(row["id"])] = str(new_id)
        print(f"  已遷移物料: {row['name']}")

    return item_map


async def main():
    print("=" * 60)
    print("開始資料遷移到 chingtech 租戶")
    print(f"租戶 ID: {TENANT_ID}")
    print("=" * 60)

    # 連接新系統資料庫
    conn = await asyncpg.connect(
        host=NEW_DB_HOST,
        port=NEW_DB_PORT,
        user=NEW_DB_USER,
        password=NEW_DB_PASSWORD,
        database=NEW_DB_NAME
    )

    try:
        # 按順序遷移資料（考慮外鍵依賴）
        vendor_map = await migrate_vendors(conn)
        user_map = await migrate_users(conn)
        project_map = await migrate_projects(conn)

        # 依賴專案的資料
        await migrate_project_members(conn, project_map, user_map)
        await migrate_project_milestones(conn, project_map)
        await migrate_project_meetings(conn, project_map)
        await migrate_project_attachments(conn, project_map)

        # Line 相關
        group_map = await migrate_line_groups(conn, project_map)
        line_user_map = await migrate_line_users(conn, user_map)

        # 庫存
        item_map = await migrate_inventory_items(conn, vendor_map)

        print("\n" + "=" * 60)
        print("資料庫遷移完成！")
        print("=" * 60)
        print(f"\n專案: {len(project_map)} 筆")
        print(f"廠商: {len(vendor_map)} 筆")
        print(f"使用者: {len(user_map)} 筆")
        print(f"Line 群組: {len(group_map)} 筆")
        print(f"Line 使用者: {len(line_user_map)} 筆")
        print(f"庫存物料: {len(item_map)} 筆")

    finally:
        await conn.close()

    print("\n接下來需要複製 NAS 檔案到租戶目錄。")
    print(f"請執行: rsync -avz ct@{OLD_SYSTEM_HOST}:/mnt/nas/ctos/linebot/ {NEW_TENANT_BASE}/linebot/")


if __name__ == "__main__":
    asyncio.run(main())
