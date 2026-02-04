#!/usr/bin/env python3
"""
專案子資料遷移腳本
將 CTOS 專案的 members、milestones、meetings、attachments、links 遷移至 ERPNext
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import asyncpg
import httpx

ERPNEXT_URL = os.environ.get("ERPNEXT_URL", "http://ct.erp")
ERPNEXT_API_KEY = os.environ["ERPNEXT_API_KEY"]
ERPNEXT_API_SECRET = os.environ["ERPNEXT_API_SECRET"]
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://ching_tech:ching_tech@localhost:5432/ching_tech_os")

DEFAULT_COMPANY = "擎添工業有限公司"

# 里程碑狀態對應
MILESTONE_STATUS_MAPPING = {
    "pending": "Open",
    "in_progress": "Working",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

# ID 映射表
id_mapping = {
    "milestones": {},  # CTOS milestone_id → ERPNext Task name
    "meetings": {},    # CTOS meeting_id → ERPNext Event name
}


async def get_project_members(conn: asyncpg.Connection, project_id: str) -> list[dict]:
    """讀取專案成員"""
    rows = await conn.fetch("""
        SELECT id, name, role, company, email, phone, notes, is_internal
        FROM project_members
        WHERE project_id = $1
        ORDER BY is_internal DESC, name
    """, project_id)
    return [dict(row) for row in rows]


async def get_project_milestones(conn: asyncpg.Connection, project_id: str) -> list[dict]:
    """讀取專案里程碑"""
    rows = await conn.fetch("""
        SELECT id, name, milestone_type, planned_date, actual_date, status, notes, sort_order
        FROM project_milestones
        WHERE project_id = $1
        ORDER BY sort_order, planned_date
    """, project_id)
    return [dict(row) for row in rows]


async def get_project_meetings(conn: asyncpg.Connection, project_id: str) -> list[dict]:
    """讀取專案會議"""
    rows = await conn.fetch("""
        SELECT id, title, meeting_date, location, attendees, content, created_by
        FROM project_meetings
        WHERE project_id = $1
        ORDER BY meeting_date
    """, project_id)
    return [dict(row) for row in rows]


async def get_project_attachments(conn: asyncpg.Connection, project_id: str) -> list[dict]:
    """讀取專案附件"""
    rows = await conn.fetch("""
        SELECT id, filename, file_type, file_size, storage_path, description, uploaded_at, uploaded_by
        FROM project_attachments
        WHERE project_id = $1
        ORDER BY uploaded_at
    """, project_id)
    return [dict(row) for row in rows]


async def get_project_links(conn: asyncpg.Connection, project_id: str) -> list[dict]:
    """讀取專案連結"""
    rows = await conn.fetch("""
        SELECT id, title, url, description
        FROM project_links
        WHERE project_id = $1
        ORDER BY created_at
    """, project_id)
    return [dict(row) for row in rows]


async def create_erpnext_task(
    client: httpx.AsyncClient,
    milestone: dict,
    project_name: str,
    dry_run: bool = False
) -> str | None:
    """將里程碑建立為 ERPNext Task"""
    task_data = {
        "subject": milestone["name"],
        "project": project_name,
        "status": MILESTONE_STATUS_MAPPING.get(milestone.get("status", "pending"), "Open"),
        "priority": "Medium",
    }

    # 預計日期（開始與結束設為同一天）
    if milestone.get("planned_date"):
        task_data["exp_start_date"] = milestone["planned_date"].isoformat()
        task_data["exp_end_date"] = milestone["planned_date"].isoformat()

    # 實際完成日期
    if milestone.get("actual_date"):
        task_data["completed_on"] = milestone["actual_date"].isoformat()

    # 備註
    if milestone.get("notes"):
        task_data["description"] = milestone["notes"]

    if dry_run:
        print(f"    [DRY-RUN] 將建立 Task: {milestone['name']}")
        return f"DRY_RUN_TASK_{milestone['id']}"

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Task",
            json={"data": json.dumps(task_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        task_name = result.get("data", {}).get("name")
        print(f"    ✓ Task: {task_name} ({milestone['name']})")
        return task_name
    except httpx.HTTPStatusError as e:
        print(f"    ✗ Task 建立失敗: {milestone['name']}")
        print(f"      錯誤: {e.response.text[:150]}")
        return None


async def create_erpnext_event(
    client: httpx.AsyncClient,
    meeting: dict,
    project_name: str,
    dry_run: bool = False
) -> str | None:
    """將會議建立為 ERPNext Event"""
    # ERPNext Event 需要 starts_on（datetime）
    meeting_dt = meeting["meeting_date"]
    if isinstance(meeting_dt, datetime):
        starts_on = meeting_dt.isoformat()
    else:
        starts_on = str(meeting_dt)

    event_data = {
        "subject": meeting["title"],
        "event_category": "Meeting",
        "event_type": "Public",
        "starts_on": starts_on,
        "all_day": 0,
    }

    # 地點
    if meeting.get("location"):
        event_data["description"] = f"地點：{meeting['location']}"

    # 會議內容加入描述
    if meeting.get("content"):
        desc = event_data.get("description", "")
        if desc:
            desc += "\n\n---\n\n"
        desc += meeting["content"]
        event_data["description"] = desc

    # 出席者（ERPNext Event 沒有 attendees 欄位，放入描述）
    if meeting.get("attendees"):
        attendees_str = "、".join(meeting["attendees"])
        desc = event_data.get("description", "")
        if desc:
            desc = f"出席：{attendees_str}\n\n{desc}"
        else:
            desc = f"出席：{attendees_str}"
        event_data["description"] = desc

    if dry_run:
        print(f"    [DRY-RUN] 將建立 Event: {meeting['title']}")
        return f"DRY_RUN_EVENT_{meeting['id']}"

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Event",
            json={"data": json.dumps(event_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        event_name = result.get("data", {}).get("name")
        print(f"    ✓ Event: {event_name} ({meeting['title']})")

        # 建立 Event 與 Project 的關聯（透過 Dynamic Link）
        await link_event_to_project(client, event_name, project_name, dry_run)

        return event_name
    except httpx.HTTPStatusError as e:
        print(f"    ✗ Event 建立失敗: {meeting['title']}")
        print(f"      錯誤: {e.response.text[:150]}")
        return None


async def link_event_to_project(
    client: httpx.AsyncClient,
    event_name: str,
    project_name: str,
    dry_run: bool = False
) -> None:
    """將 Event 關聯到 Project（透過 Event Participants）"""
    if dry_run:
        return

    try:
        # 更新 Event 加入 event_participants
        resp = await client.put(
            f"{ERPNEXT_URL}/api/resource/Event/{event_name}",
            json={"data": json.dumps({
                "event_participants": [{
                    "reference_doctype": "Project",
                    "reference_docname": project_name,
                }]
            })},
        )
        resp.raise_for_status()
    except Exception:
        # 關聯失敗不影響主流程
        pass


async def create_project_comment(
    client: httpx.AsyncClient,
    project_name: str,
    comment_type: str,
    content: str,
    dry_run: bool = False
) -> None:
    """在專案下建立 Comment（用於存放附件和連結資訊）"""
    if dry_run:
        print(f"    [DRY-RUN] 將建立 Comment: {comment_type}")
        return

    try:
        comment_data = {
            "reference_doctype": "Project",
            "reference_name": project_name,
            "comment_type": "Info",
            "content": content,
        }
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Comment",
            json={"data": json.dumps(comment_data)},
        )
        resp.raise_for_status()
        print(f"    ✓ Comment: {comment_type}")
    except httpx.HTTPStatusError as e:
        print(f"    ⚠ Comment 建立失敗: {comment_type}")


async def migrate_project_subdata(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    ctos_project_id: str,
    erpnext_project_name: str,
    dry_run: bool = False
) -> dict:
    """遷移單一專案的子資料"""
    result = {
        "members": 0,
        "milestones": 0,
        "meetings": 0,
        "attachments": 0,
        "links": 0,
    }

    # 1. 遷移成員（建立為 Comment 摘要）
    members = await get_project_members(conn, ctos_project_id)
    if members:
        members_content = "<h4>專案成員（從 CTOS 遷移）</h4><ul>"
        for m in members:
            member_info = f"<li><strong>{m['name']}</strong>"
            if m.get("role"):
                member_info += f" - {m['role']}"
            if m.get("company"):
                member_info += f" ({m['company']})"
            if m.get("email"):
                member_info += f" | {m['email']}"
            if m.get("phone"):
                member_info += f" | {m['phone']}"
            member_info += "</li>"
            members_content += member_info
        members_content += "</ul>"

        await create_project_comment(client, erpnext_project_name, "專案成員", members_content, dry_run)
        result["members"] = len(members)
        if not dry_run:
            print(f"    成員: {len(members)} 人")

    # 2. 遷移里程碑（建立為 Task）
    milestones = await get_project_milestones(conn, ctos_project_id)
    for milestone in milestones:
        task_name = await create_erpnext_task(client, milestone, erpnext_project_name, dry_run)
        if task_name:
            id_mapping["milestones"][str(milestone["id"])] = task_name
            result["milestones"] += 1

    # 3. 遷移會議（建立為 Event）
    meetings = await get_project_meetings(conn, ctos_project_id)
    for meeting in meetings:
        event_name = await create_erpnext_event(client, meeting, erpnext_project_name, dry_run)
        if event_name:
            id_mapping["meetings"][str(meeting["id"])] = event_name
            result["meetings"] += 1

    # 4. 遷移附件（保留 NAS 路徑，建立為 Comment）
    attachments = await get_project_attachments(conn, ctos_project_id)
    if attachments:
        attachments_content = "<h4>專案附件（NAS 路徑）</h4><ul>"
        for att in attachments:
            att_info = f"<li><strong>{att['filename']}</strong>"
            if att.get("description"):
                att_info += f" - {att['description']}"
            att_info += f"<br/>路徑: <code>{att['storage_path']}</code>"
            if att.get("file_size"):
                size_mb = att["file_size"] / 1024 / 1024
                att_info += f" ({size_mb:.2f} MB)"
            att_info += "</li>"
            attachments_content += att_info
        attachments_content += "</ul>"

        await create_project_comment(client, erpnext_project_name, "專案附件", attachments_content, dry_run)
        result["attachments"] = len(attachments)
        if not dry_run:
            print(f"    附件: {len(attachments)} 個（保留 NAS 路徑）")

    # 5. 遷移連結（建立為 Comment）
    links = await get_project_links(conn, ctos_project_id)
    if links:
        links_content = "<h4>相關連結</h4><ul>"
        for link in links:
            link_info = f'<li><a href="{link["url"]}">{link["title"]}</a>'
            if link.get("description"):
                link_info += f" - {link['description']}"
            link_info += "</li>"
            links_content += link_info
        links_content += "</ul>"

        await create_project_comment(client, erpnext_project_name, "相關連結", links_content, dry_run)
        result["links"] = len(links)
        if not dry_run:
            print(f"    連結: {len(links)} 個")

    return result


async def migrate_all_project_data(
    project_mapping: dict = None,
    mapping_file: str = None,
    dry_run: bool = False
) -> dict:
    """執行所有專案子資料遷移"""
    print("=" * 50)
    print("專案子資料遷移 (members, milestones, meetings, attachments, links)")
    print("=" * 50)

    # 讀取專案映射
    if project_mapping is None and mapping_file:
        with open(mapping_file) as f:
            mapping_data = json.load(f)
            project_mapping = mapping_data.get("projects", {})

    if not project_mapping:
        print("\n錯誤：需要專案映射表（由 migrate_projects.py 產生）")
        return id_mapping

    print(f"\n找到 {len(project_mapping)} 個專案需要遷移子資料\n")

    # 連接 CTOS 資料庫
    conn = await asyncpg.connect(DATABASE_URL)

    # 建立 ERPNext client
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
    }

    total_stats = {
        "members": 0,
        "milestones": 0,
        "meetings": 0,
        "attachments": 0,
        "links": 0,
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        for ctos_id, erpnext_name in project_mapping.items():
            print(f"\n處理專案: {erpnext_name} (CTOS ID: {ctos_id})")

            result = await migrate_project_subdata(
                conn, client, ctos_id, erpnext_name, dry_run
            )

            for key in total_stats:
                total_stats[key] += result[key]

    await conn.close()

    print("\n" + "=" * 50)
    print("遷移統計:")
    print(f"  成員: {total_stats['members']} 人")
    print(f"  里程碑 → Task: {total_stats['milestones']} 個")
    print(f"  會議 → Event: {total_stats['meetings']} 個")
    print(f"  附件: {total_stats['attachments']} 個")
    print(f"  連結: {total_stats['links']} 個")

    return id_mapping


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="遷移 CTOS 專案子資料到 ERPNext")
    parser.add_argument("--mapping-file", type=str, required=True,
                        help="專案映射表 JSON 檔案路徑（由 migrate_projects.py 產生）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只顯示將執行的操作，不實際執行")
    args = parser.parse_args()

    result = asyncio.run(migrate_all_project_data(
        mapping_file=args.mapping_file,
        dry_run=args.dry_run,
    ))

    if not args.dry_run:
        print("\nID 映射表:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
