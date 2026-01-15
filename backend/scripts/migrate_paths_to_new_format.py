"""遷移腳本：將舊格式路徑轉換為新格式

此腳本會更新：
1. 知識庫 markdown 檔案中的附件路徑
2. 資料庫中 project_attachments.storage_path

舊格式 → 新格式：
- nas://knowledge/attachments/xxx → ctos://knowledge/xxx
- nas://knowledge/xxx → ctos://knowledge/xxx
- nas://linebot/files/xxx → ctos://linebot/xxx
- nas://projects/attachments/xxx → ctos://attachments/xxx
- ../assets/images/xxx → local://knowledge/images/xxx
- ../assets/xxx → local://knowledge/xxx

執行方式：
    cd backend && uv run python scripts/migrate_paths_to_new_format.py [--dry-run]
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

# 加入專案路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ching_tech_os.config import settings
from ching_tech_os.database import init_db_pool, get_pool, close_db_pool

# 知識庫路徑
KNOWLEDGE_PATH = Path(settings.knowledge_data_path) / "entries"

# 路徑轉換規則
PATH_CONVERSIONS = [
    # 舊格式 nas:// 轉換
    (r"nas://knowledge/attachments/", "ctos://knowledge/"),
    (r"nas://knowledge/", "ctos://knowledge/"),
    (r"nas://linebot/files/", "ctos://linebot/"),
    (r"nas://linebot/", "ctos://linebot/"),
    (r"nas://projects/attachments/", "ctos://projects/attachments/"),
    (r"nas://projects/", "ctos://projects/"),
    (r"nas://ching-tech-os/linebot/files/", "ctos://linebot/"),
    # 本機相對路徑轉換
    (r"\.\./assets/images/", "local://knowledge/images/"),
    (r"\.\./assets/", "local://knowledge/"),
]


def convert_path(path: str) -> tuple[str, bool]:
    """轉換單個路徑

    Returns:
        (new_path, changed): 新路徑和是否有變更
    """
    original = path
    for pattern, replacement in PATH_CONVERSIONS:
        path = re.sub(pattern, replacement, path)

    return path, path != original


def update_knowledge_files(dry_run: bool = True) -> dict:
    """更新知識庫 markdown 檔案

    Returns:
        統計資訊
    """
    stats = {"files_checked": 0, "files_updated": 0, "paths_converted": 0}

    if not KNOWLEDGE_PATH.exists():
        print(f"知識庫目錄不存在: {KNOWLEDGE_PATH}")
        return stats

    for md_file in KNOWLEDGE_PATH.glob("*.md"):
        stats["files_checked"] += 1
        content = md_file.read_text(encoding="utf-8")
        new_content = content
        file_changed = False

        # 尋找並轉換 path: xxx 格式
        for pattern, replacement in PATH_CONVERSIONS:
            matches = re.findall(rf"path:\s*({pattern}[^\n]*)", content)
            for match in matches:
                new_path, changed = convert_path(match)
                if changed:
                    new_content = new_content.replace(match, new_path)
                    file_changed = True
                    stats["paths_converted"] += 1
                    print(f"  轉換: {match[:60]}...")
                    print(f"     → {new_path[:60]}...")

        if file_changed:
            stats["files_updated"] += 1
            print(f"\n檔案: {md_file.name}")
            if not dry_run:
                md_file.write_text(new_content, encoding="utf-8")
                print("  [已更新]")
            else:
                print("  [dry-run 模式，未實際修改]")

    return stats


async def update_database(dry_run: bool = True) -> dict:
    """更新資料庫中的路徑

    Returns:
        統計資訊
    """
    stats = {"rows_checked": 0, "rows_updated": 0}

    # 初始化資料庫連線池
    await init_db_pool()
    pool = get_pool()

    try:
        # 更新 project_attachments
        rows = await pool.fetch(
            """
            SELECT id, storage_path FROM project_attachments
            WHERE storage_path LIKE 'nas://%'
            """
        )

        stats["rows_checked"] = len(rows)

        for row in rows:
            new_path, changed = convert_path(row["storage_path"])
            if changed:
                stats["rows_updated"] += 1
                print(f"\nproject_attachments[{row['id']}]:")
                print(f"  舊: {row['storage_path']}")
                print(f"  新: {new_path}")

                if not dry_run:
                    await pool.execute(
                        "UPDATE project_attachments SET storage_path = $1 WHERE id = $2",
                        new_path,
                        row["id"],
                    )
                    print("  [已更新]")
                else:
                    print("  [dry-run 模式，未實際修改]")
    finally:
        await close_db_pool()

    return stats


async def main():
    parser = argparse.ArgumentParser(description="遷移舊格式路徑為新格式")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="僅顯示會進行的變更，不實際修改",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("路徑格式遷移腳本")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY-RUN 模式] 僅顯示變更，不實際修改\n")
    else:
        print("\n[執行模式] 將實際修改檔案和資料庫\n")
        confirm = input("確定要執行嗎？ (yes/no): ")
        if confirm.lower() != "yes":
            print("已取消")
            return

    # 更新知識庫檔案
    print("\n--- 知識庫 Markdown 檔案 ---")
    kb_stats = update_knowledge_files(dry_run=args.dry_run)
    print(f"\n檢查: {kb_stats['files_checked']} 個檔案")
    print(f"更新: {kb_stats['files_updated']} 個檔案")
    print(f"轉換: {kb_stats['paths_converted']} 個路徑")

    # 更新資料庫
    print("\n--- 資料庫 project_attachments ---")
    db_stats = await update_database(dry_run=args.dry_run)
    print(f"\n檢查: {db_stats['rows_checked']} 筆記錄")
    print(f"更新: {db_stats['rows_updated']} 筆記錄")

    print("\n" + "=" * 60)
    print("完成！")
    if args.dry_run:
        print("這是 dry-run 模式，沒有實際修改任何資料")
        print("確認無誤後，請移除 --dry-run 參數重新執行")


if __name__ == "__main__":
    asyncio.run(main())
