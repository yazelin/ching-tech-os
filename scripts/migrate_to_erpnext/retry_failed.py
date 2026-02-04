#!/usr/bin/env python3
"""
重新遷移失敗的里程碑和會議
"""
import asyncio
import json
import os
from datetime import datetime

import asyncpg
import httpx

ERPNEXT_URL = os.environ.get("ERPNEXT_URL", "http://ct.erp")
ERPNEXT_API_KEY = os.environ["ERPNEXT_API_KEY"]
ERPNEXT_API_SECRET = os.environ["ERPNEXT_API_SECRET"]
DATABASE_URL = os.environ.get("DATABASE_URL")

MAPPING_FILE = os.path.join(os.path.dirname(__file__), "id_mapping.json")

# 里程碑狀態對應
MILESTONE_STATUS_MAPPING = {
    "pending": "Open",
    "in_progress": "Working",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


async def get_existing_tasks(client: httpx.AsyncClient, project_name: str) -> set[str]:
    """取得專案已存在的 Task 名稱"""
    try:
        resp = await client.get(
            f"{ERPNEXT_URL}/api/resource/Task",
            params={
                "filters": json.dumps([["project", "=", project_name]]),
                "fields": json.dumps(["subject"]),
                "limit_page_length": 0,
            }
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return {task["subject"] for task in data}
    except Exception:
        return set()


async def create_task(
    client: httpx.AsyncClient,
    milestone: dict,
    project_name: str,
) -> str | None:
    """建立 Task"""
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

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Task",
            json={"data": json.dumps(task_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        task_name = result.get("data", {}).get("name")
        print(f"  ✓ Task: {task_name} ({milestone['name']})")
        return task_name
    except httpx.HTTPStatusError as e:
        print(f"  ✗ Task 建立失敗: {milestone['name']}")
        print(f"    錯誤: {e.response.text[:200]}")
        return None


async def create_event(
    client: httpx.AsyncClient,
    meeting: dict,
    project_name: str,
) -> str | None:
    """建立 Event"""
    meeting_dt = meeting["meeting_date"]
    if isinstance(meeting_dt, datetime):
        # ERPNext 不接受帶時區的 ISO 格式，轉換為不帶時區的格式
        starts_on = meeting_dt.strftime("%Y-%m-%d %H:%M:%S")
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

    # 會議內容
    if meeting.get("content"):
        desc = event_data.get("description", "")
        if desc:
            desc += "\n\n---\n\n"
        desc += meeting["content"]
        event_data["description"] = desc

    # 出席者
    if meeting.get("attendees"):
        attendees_str = "、".join(meeting["attendees"])
        desc = event_data.get("description", "")
        if desc:
            desc = f"出席：{attendees_str}\n\n{desc}"
        else:
            desc = f"出席：{attendees_str}"
        event_data["description"] = desc

    try:
        resp = await client.post(
            f"{ERPNEXT_URL}/api/resource/Event",
            json={"data": json.dumps(event_data)},
        )
        resp.raise_for_status()
        result = resp.json()
        event_name = result.get("data", {}).get("name")
        print(f"  ✓ Event: {event_name} ({meeting['title']})")

        # 關聯到專案
        try:
            await client.put(
                f"{ERPNEXT_URL}/api/resource/Event/{event_name}",
                json={"data": json.dumps({
                    "event_participants": [{
                        "reference_doctype": "Project",
                        "reference_docname": project_name,
                    }]
                })},
            )
        except Exception:
            pass

        return event_name
    except httpx.HTTPStatusError as e:
        print(f"  ✗ Event 建立失敗: {meeting['title']}")
        print(f"    錯誤: {e.response.text[:200]}")
        return None


async def retry_failed():
    """重新遷移失敗的資料"""
    print("=" * 50)
    print("重新遷移失敗的里程碑和會議")
    print("=" * 50)

    # 讀取映射表
    with open(MAPPING_FILE) as f:
        mapping = json.load(f)

    project_mapping = mapping.get("projects", {})
    existing_milestones = set(mapping.get("milestones", {}).keys())
    existing_meetings = set(mapping.get("meetings", {}).keys())

    # 連接資料庫
    conn = await asyncpg.connect(DATABASE_URL)

    # 建立 ERPNext client
    headers = {
        "Authorization": f"token {ERPNEXT_API_KEY}:{ERPNEXT_API_SECRET}",
        "Content-Type": "application/json",
    }

    new_milestones = {}
    new_meetings = {}

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        for ctos_project_id, erpnext_project_name in project_mapping.items():
            print(f"\n專案: {erpnext_project_name}")

            # 取得已存在的 Task 名稱
            existing_task_subjects = await get_existing_tasks(client, erpnext_project_name)

            # 查詢尚未遷移的里程碑
            milestones = await conn.fetch("""
                SELECT id, name, milestone_type, planned_date, actual_date, status, notes
                FROM project_milestones
                WHERE project_id = $1
                ORDER BY planned_date
            """, ctos_project_id)

            for row in milestones:
                milestone = dict(row)
                milestone_id = str(milestone["id"])

                # 跳過已遷移的
                if milestone_id in existing_milestones:
                    continue

                # 跳過已存在的（可能是之前手動建立的）
                if milestone["name"] in existing_task_subjects:
                    print(f"  - 略過（已存在）: {milestone['name']}")
                    continue

                task_name = await create_task(client, milestone, erpnext_project_name)
                if task_name:
                    new_milestones[milestone_id] = task_name

            # 查詢尚未遷移的會議
            meetings = await conn.fetch("""
                SELECT id, title, meeting_date, location, attendees, content
                FROM project_meetings
                WHERE project_id = $1
                ORDER BY meeting_date
            """, ctos_project_id)

            for row in meetings:
                meeting = dict(row)
                meeting_id = str(meeting["id"])

                # 跳過已遷移的
                if meeting_id in existing_meetings:
                    continue

                event_name = await create_event(client, meeting, erpnext_project_name)
                if event_name:
                    new_meetings[meeting_id] = event_name

    await conn.close()

    # 更新映射表
    if new_milestones or new_meetings:
        mapping["milestones"].update(new_milestones)
        mapping["meetings"].update(new_meetings)

        with open(MAPPING_FILE, "w") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 映射表已更新: {MAPPING_FILE}")

    print("\n" + "=" * 50)
    print("重新遷移統計:")
    print(f"  新增里程碑 → Task: {len(new_milestones)} 個")
    print(f"  新增會議 → Event: {len(new_meetings)} 個")


if __name__ == "__main__":
    asyncio.run(retry_failed())
