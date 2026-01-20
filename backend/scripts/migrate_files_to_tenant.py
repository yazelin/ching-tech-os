#!/usr/bin/env python3
"""檔案遷移腳本：將現有檔案移至租戶目錄

此腳本將現有的 CTOS 檔案從舊結構遷移到多租戶結構。

舊結構：
/mnt/nas/ctos/
├── knowledge/
├── linebot/
├── attachments/
└── ...

新結構：
/mnt/nas/ctos/
├── system/           # 系統檔案（跨租戶）
└── tenants/
    └── {default-tenant-id}/
        ├── knowledge/
        ├── linebot/
        ├── attachments/
        └── ai-generated/

使用方式：
    # 預覽模式（不執行實際操作）
    python scripts/migrate_files_to_tenant.py --dry-run

    # 執行遷移
    python scripts/migrate_files_to_tenant.py

    # 執行遷移並建立符號連結（向後相容）
    python scripts/migrate_files_to_tenant.py --create-symlinks
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

# 預設租戶 UUID
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"

# CTOS 掛載路徑
CTOS_MOUNT_PATH = os.getenv("CTOS_MOUNT_PATH", "/mnt/nas/ctos")

# 需要遷移的目錄
DIRECTORIES_TO_MIGRATE = [
    "knowledge",
    "linebot",
    "attachments",
    "projects",
    "ai-generated",
]


def get_tenant_base_path(tenant_id: str = DEFAULT_TENANT_ID) -> Path:
    """取得租戶基礎路徑"""
    return Path(CTOS_MOUNT_PATH) / "tenants" / tenant_id


def ensure_directory_structure(tenant_id: str = DEFAULT_TENANT_ID) -> None:
    """確保租戶目錄結構存在"""
    base = get_tenant_base_path(tenant_id)

    # 建立租戶子目錄
    for dir_name in DIRECTORIES_TO_MIGRATE:
        dir_path = base / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ 確保目錄存在: {dir_path}")


def migrate_directory(
    source: Path,
    dest: Path,
    dry_run: bool = True,
    create_symlink: bool = False,
) -> bool:
    """遷移單一目錄

    Args:
        source: 來源目錄
        dest: 目標目錄
        dry_run: 是否為預覽模式
        create_symlink: 是否在來源位置建立符號連結

    Returns:
        True 如果成功，False 否則
    """
    # 檢查來源是否存在
    if not source.exists():
        print(f"  ⚠ 來源目錄不存在，跳過: {source}")
        return True

    # 如果來源是符號連結，跳過（可能已經遷移過）
    if source.is_symlink():
        print(f"  ⚠ 來源是符號連結，跳過: {source}")
        return True

    # 如果目標已存在且有內容，警告
    if dest.exists() and any(dest.iterdir()):
        print(f"  ⚠ 目標目錄已有內容: {dest}")
        if not dry_run:
            # 合併內容而不是覆蓋
            print(f"    將合併 {source} 到 {dest}")

    if dry_run:
        print(f"  [預覽] 將遷移: {source} → {dest}")
        if create_symlink:
            print(f"  [預覽] 將建立符號連結: {source} → {dest}")
        return True

    try:
        # 確保目標父目錄存在
        dest.parent.mkdir(parents=True, exist_ok=True)

        # 如果目標不存在，直接移動
        if not dest.exists():
            shutil.move(str(source), str(dest))
            print(f"  ✓ 已遷移: {source} → {dest}")
        else:
            # 目標存在，逐一移動內容
            for item in source.iterdir():
                item_dest = dest / item.name
                if item_dest.exists():
                    print(f"    ⚠ 跳過已存在的項目: {item.name}")
                else:
                    shutil.move(str(item), str(item_dest))
                    print(f"    ✓ 已移動: {item.name}")

            # 如果來源目錄為空，刪除它
            if not any(source.iterdir()):
                source.rmdir()
                print(f"  ✓ 已刪除空目錄: {source}")

        # 建立符號連結
        if create_symlink and not source.exists():
            os.symlink(str(dest), str(source))
            print(f"  ✓ 已建立符號連結: {source} → {dest}")

        return True

    except Exception as e:
        print(f"  ✗ 遷移失敗: {e}")
        return False


def run_migration(
    tenant_id: str = DEFAULT_TENANT_ID,
    dry_run: bool = True,
    create_symlinks: bool = False,
) -> bool:
    """執行檔案遷移

    Args:
        tenant_id: 目標租戶 ID
        dry_run: 是否為預覽模式
        create_symlinks: 是否建立符號連結

    Returns:
        True 如果全部成功，False 否則
    """
    ctos_path = Path(CTOS_MOUNT_PATH)
    tenant_base = get_tenant_base_path(tenant_id)

    print(f"\n{'='*60}")
    print(f"檔案遷移腳本")
    print(f"{'='*60}")
    print(f"CTOS 路徑: {ctos_path}")
    print(f"租戶 ID: {tenant_id}")
    print(f"租戶路徑: {tenant_base}")
    print(f"模式: {'預覽' if dry_run else '執行'}")
    print(f"建立符號連結: {'是' if create_symlinks else '否'}")
    print(f"{'='*60}\n")

    # 檢查 CTOS 路徑
    if not ctos_path.exists():
        print(f"✗ CTOS 路徑不存在: {ctos_path}")
        return False

    # 確保目錄結構
    print("步驟 1: 確保租戶目錄結構")
    if not dry_run:
        ensure_directory_structure(tenant_id)
    else:
        print(f"  [預覽] 將建立目錄: {tenant_base}")
        for dir_name in DIRECTORIES_TO_MIGRATE:
            print(f"  [預覽] 將建立目錄: {tenant_base / dir_name}")

    # 遷移目錄
    print("\n步驟 2: 遷移檔案")
    all_success = True
    for dir_name in DIRECTORIES_TO_MIGRATE:
        source = ctos_path / dir_name
        dest = tenant_base / dir_name

        print(f"\n處理目錄: {dir_name}")
        success = migrate_directory(source, dest, dry_run, create_symlinks)
        if not success:
            all_success = False

    # 建立 system 目錄（跨租戶共用）
    print("\n步驟 3: 建立系統目錄")
    system_path = ctos_path / "system"
    if not dry_run:
        system_path.mkdir(parents=True, exist_ok=True)
        (system_path / "templates").mkdir(exist_ok=True)
        (system_path / "defaults").mkdir(exist_ok=True)
        print(f"  ✓ 已建立系統目錄: {system_path}")
    else:
        print(f"  [預覽] 將建立系統目錄: {system_path}")

    print(f"\n{'='*60}")
    if all_success:
        if dry_run:
            print("預覽完成！使用 --no-dry-run 執行實際遷移")
        else:
            print("遷移完成！")
    else:
        print("遷移過程中有錯誤發生，請檢查上方訊息")
    print(f"{'='*60}\n")

    return all_success


def main():
    parser = argparse.ArgumentParser(
        description="將 CTOS 檔案遷移至多租戶目錄結構",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--tenant-id",
        default=DEFAULT_TENANT_ID,
        help=f"目標租戶 ID（預設：{DEFAULT_TENANT_ID}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="預覽模式，不執行實際操作",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="執行實際遷移（預設為預覽模式）",
    )
    parser.add_argument(
        "--create-symlinks",
        action="store_true",
        help="在原位置建立符號連結（向後相容）",
    )

    args = parser.parse_args()

    # 預設為 dry-run，除非明確指定 --no-dry-run
    dry_run = not args.no_dry_run

    success = run_migration(
        tenant_id=args.tenant_id,
        dry_run=dry_run,
        create_symlinks=args.create_symlinks,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
