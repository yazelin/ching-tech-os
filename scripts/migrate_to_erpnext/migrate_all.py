#!/usr/bin/env python3
"""
ERPNext 資料遷移主程式
整合所有遷移腳本，支援 dry-run 模式和階段執行
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 確保可以載入同目錄的模組
sys.path.insert(0, str(Path(__file__).parent))

from mapping_manager import MappingManager
from migrate_vendors import migrate_vendors
from migrate_items import migrate_items
from migrate_projects import migrate_projects
from migrate_project_data import migrate_all_project_data
from create_opening_stock import create_opening_stock


async def run_full_migration(
    dry_run: bool = False,
    skip_vendors: bool = False,
    skip_items: bool = False,
    skip_stock: bool = False,
    skip_projects: bool = False,
    skip_project_data: bool = False,
    auto_submit_stock: bool = False,
    mapping_file: str = None,
) -> dict:
    """
    執行完整資料遷移

    Args:
        dry_run: 只顯示將執行的操作，不實際執行
        skip_vendors: 跳過廠商遷移
        skip_items: 跳過物料遷移
        skip_stock: 跳過期初庫存建立
        skip_projects: 跳過專案遷移
        skip_project_data: 跳過專案子資料遷移
        auto_submit_stock: 自動提交 Stock Entry
        mapping_file: 指定映射表檔案路徑
    """
    print("=" * 60)
    print("CTOS → ERPNext 資料遷移")
    print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if dry_run:
        print("模式: DRY-RUN（不實際執行）")
    print("=" * 60)

    # 初始化映射表管理器
    manager = MappingManager(mapping_file)

    # 階段 1: 廠商遷移
    if not skip_vendors:
        print("\n" + "=" * 60)
        print("階段 1/5: 廠商遷移")
        print("=" * 60)
        vendor_result = await migrate_vendors(dry_run=dry_run)
        if not dry_run:
            manager.merge(vendor_result)
    else:
        print("\n[SKIP] 廠商遷移")

    # 階段 2: 物料遷移
    if not skip_items:
        print("\n" + "=" * 60)
        print("階段 2/5: 物料遷移")
        print("=" * 60)
        item_result = await migrate_items(
            vendor_mapping=manager.get_vendors(),
            dry_run=dry_run
        )
        if not dry_run:
            manager.merge(item_result)
    else:
        print("\n[SKIP] 物料遷移")

    # 階段 3: 期初庫存
    if not skip_stock and not skip_items:
        print("\n" + "=" * 60)
        print("階段 3/5: 期初庫存建立")
        print("=" * 60)
        items_with_stock = manager.get_items_with_stock()
        if items_with_stock:
            stock_result = await create_opening_stock(
                items_with_stock=items_with_stock,
                auto_submit=auto_submit_stock,
                dry_run=dry_run
            )
            if not dry_run and stock_result.get("stock_entry"):
                manager.mapping["stock_entry"] = stock_result
        else:
            print("沒有需要建立期初庫存的物料")
    else:
        print("\n[SKIP] 期初庫存建立")

    # 階段 4: 專案遷移
    if not skip_projects:
        print("\n" + "=" * 60)
        print("階段 4/5: 專案遷移")
        print("=" * 60)
        project_result = await migrate_projects(dry_run=dry_run)
        if not dry_run:
            manager.merge(project_result)
    else:
        print("\n[SKIP] 專案遷移")

    # 階段 5: 專案子資料遷移
    if not skip_project_data and not skip_projects:
        print("\n" + "=" * 60)
        print("階段 5/5: 專案子資料遷移")
        print("=" * 60)
        project_data_result = await migrate_all_project_data(
            project_mapping=manager.get_projects(),
            dry_run=dry_run
        )
        if not dry_run:
            manager.merge(project_data_result)
    else:
        print("\n[SKIP] 專案子資料遷移")

    # 儲存映射表
    if not dry_run:
        manager.save()

    # 顯示摘要
    print("\n" + manager.summary())

    print("\n" + "=" * 60)
    print(f"遷移完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    return manager.mapping


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CTOS → ERPNext 資料遷移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # Dry-run 模式（檢視將執行的操作）
  python migrate_all.py --dry-run

  # 只遷移廠商和物料
  python migrate_all.py --skip-projects --skip-project-data --skip-stock

  # 完整遷移並自動提交庫存
  python migrate_all.py --auto-submit-stock

  # 從現有映射表繼續
  python migrate_all.py --mapping-file ./existing_mapping.json --skip-vendors --skip-items
        """
    )

    parser.add_argument("--dry-run", action="store_true",
                        help="只顯示將執行的操作，不實際執行")
    parser.add_argument("--skip-vendors", action="store_true",
                        help="跳過廠商遷移")
    parser.add_argument("--skip-items", action="store_true",
                        help="跳過物料遷移")
    parser.add_argument("--skip-stock", action="store_true",
                        help="跳過期初庫存建立")
    parser.add_argument("--skip-projects", action="store_true",
                        help="跳過專案遷移")
    parser.add_argument("--skip-project-data", action="store_true",
                        help="跳過專案子資料遷移")
    parser.add_argument("--auto-submit-stock", action="store_true",
                        help="自動提交 Stock Entry（期初庫存）")
    parser.add_argument("--mapping-file", type=str,
                        help="指定映射表檔案路徑")

    args = parser.parse_args()

    # 檢查環境變數
    required_env = ["ERPNEXT_API_KEY", "ERPNEXT_API_SECRET"]
    missing = [e for e in required_env if e not in os.environ]
    if missing:
        print(f"錯誤：缺少環境變數: {', '.join(missing)}")
        print("\n請設定以下環境變數：")
        print("  export ERPNEXT_API_KEY=your_api_key")
        print("  export ERPNEXT_API_SECRET=your_api_secret")
        print("  export ERPNEXT_URL=http://ct.erp  # 可選")
        print("  export DATABASE_URL=postgresql://...  # 可選")
        sys.exit(1)

    result = asyncio.run(run_full_migration(
        dry_run=args.dry_run,
        skip_vendors=args.skip_vendors,
        skip_items=args.skip_items,
        skip_stock=args.skip_stock,
        skip_projects=args.skip_projects,
        skip_project_data=args.skip_project_data,
        auto_submit_stock=args.auto_submit_stock,
        mapping_file=args.mapping_file,
    ))

    if not args.dry_run:
        # 輸出完整映射表到 stdout（可重定向到檔案）
        print("\n\n--- JSON 映射表 ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
