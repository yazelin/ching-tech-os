#!/usr/bin/env python3
"""
專案資料遷移腳本
將 CTOS projects 資料遷移至 ERPNext Project
"""
import asyncio
import json
import os
from pathlib import Path

import asyncpg
import httpx

ERPNEXT_URL = os.environ.get("ERPNEXT_URL", "http://ct.erp")
ERPNEXT_API_KEY = os.environ["ERPNEXT_API_KEY"]
ERPNEXT_API_SECRET = os.environ["ERPNEXT_API_SECRET"]
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://ching_tech:ching_tech@localhost:5432/ching_tech_os")

# 預設公司
DEFAULT_COMPANY = "擎添工業有限公司"

# 狀態對應表（CTOS → ERPNext）
STATUS_MAPPING = {
    "active": "Open",
    "completed": "Completed",
    "on_hold": "Open",  # ERPNext 沒有暫停狀態，用 Open 替代
    "cancelled": "Cancelled",
}

# ID 映射表
id_mapping = {
    "projects": {},
    "milestones": {},
    "meetings": {},
}


async def get_ctos_projects(conn: asyncpg.Connection) -> list[dict]:
    """從 CTOS 讀取所有專案資料"""
    rows = await conn.fetch("""
        SELECT id, name, description, status, start_date, end_date,
               created_at, updated_at, created_by
        FROM projects
        ORDER BY created_at
    """)
    return [dict(row) for row in rows]


async def create_erpnext_project(
    client: httpx.AsyncClient,
    project: dict,
    dry_run: bool = False
) -> str | None:
    """在 ERPNext 建立 Project"""
    # 建立專案代碼（使用 CTOS ID 前 8 碼）
    project_id = str(project["id"])[:8].upper()

    project_data = {
        "project_name": project["name"],
        "company": DEFAULT_COMPANY,
        "status": STATUS_MAPPING.get(project.get("status", "active"), "Open"),
        "is_active": "Yes" if project.get("status") == "active" else "No",
    }

    # 專案說明
    if project.get("description"):
        project_data["notes"] = project["description"]

    # 預期開始/結束日期
    if project.get("start_date"):
        project_data["expected_start_date"] = project["start_date"].isoformat()
    if project.get("end_date"):
        project_data["expected_end_date"] = project["end_date"].isoformat()

    if dry_run:
        print(f"  [DRY-RUN] 將建立 Project: {project['name']}")
        print(f"    狀態: {project_data['status']}")
        if project.get("start_date"):
            print(f"    開始: {project_data['expected_start_date']}")
        if project.get("end_date"):
            print(f"    結束: {project_data['expected_end_date']}")
        return f"DRY_RUN_{project_id}"

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Project",
            json={"data": json.dumps(project_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        project_name = result.get("data", {}).get("name")
        print(f"  ✓ 建立 Project: {project_name}")
        return project_name
    except httpx.HTTPStatusError as e:
        print(f"  ✗ 建立 Project 失敗: {project['name']}")
        print(f"    錯誤: {e.response.text[:200]}")
        return None


async def migrate_projects(dry_run: bool = False) -> dict:
    """執行專案遷移（僅專案主資料）"""
    print("=" * 50)
    print("專案遷移 (projects → Project)")
    print("=" * 50)

    # 連接 CTOS 資料庫
    conn = await asyncpg.connect(DATABASE_URL)

    # 建立 ERPNext client
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # 讀取 CTOS 專案
        projects = await get_ctos_projects(conn)
        print(f"\n找到 {len(projects)} 筆專案資料\n")

        success_count = 0
        for project in projects:
            print(f"\n處理: {project['name']} (ID: {project['id']})")

            # 建立 Project
            project_name = await create_erpnext_project(client, project, dry_run)

            if project_name:
                # 記錄 ID 映射
                id_mapping["projects"][str(project["id"])] = project_name
                success_count += 1

        print(f"\n完成：{success_count}/{len(projects)} 筆")

    await conn.close()
    return id_mapping


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="遷移 CTOS 專案到 ERPNext")
    parser.add_argument("--dry-run", action="store_true", help="只顯示將執行的操作，不實際執行")
    args = parser.parse_args()

    result = asyncio.run(migrate_projects(dry_run=args.dry_run))

    if not args.dry_run:
        print("\nID 映射表:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
