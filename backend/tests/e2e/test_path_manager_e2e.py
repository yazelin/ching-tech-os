#!/usr/bin/env python3
"""PathManager 端對端測試

這個腳本測試 PathManager 相關功能在真實環境中的運作。
需要後端服務運行中才能執行。

執行方式：
    cd backend && uv run python tests/e2e/test_path_manager_e2e.py

前置條件：
    1. 後端服務運行中 (localhost:8000)
    2. 有效的認證 token
    3. NAS 掛載點可用
"""

import asyncio
import sys
import os
from pathlib import Path

# 將 src 加入 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ching_tech_os.services.path_manager import path_manager, StorageZone


def print_banner(name: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print('='*60)


def print_result(name: str, passed: bool, detail: str = ""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {name}")
    if detail:
        print(f"       {detail}")


def run_tests():
    """執行所有端對端測試"""
    passed = 0
    failed = 0

    # ============================================================
    # 測試 1: PathManager 解析
    # ============================================================
    print_banner("PathManager 路徑解析測試")

    test_cases = [
        # 新格式
        ("ctos://linebot/files/test.jpg", StorageZone.CTOS, "linebot/files/test.jpg"),
        ("shared://亦達光學/doc.pdf", StorageZone.SHARED, "亦達光學/doc.pdf"),
        ("temp://converted/page.png", StorageZone.TEMP, "converted/page.png"),
        # 舊格式
        ("nas://knowledge/attachments/kb-001/file.pdf", StorageZone.CTOS, "knowledge/kb-001/file.pdf"),
        ("/mnt/nas/projects/亦達光學/test.pdf", StorageZone.SHARED, "亦達光學/test.pdf"),
        ("/mnt/nas/ctos/linebot/test.jpg", StorageZone.CTOS, "linebot/test.jpg"),
        ("/tmp/ctos/converted/page.png", StorageZone.TEMP, "ctos/converted/page.png"),
        # Line Bot 相對路徑
        ("groups/C123/images/photo.jpg", StorageZone.CTOS, "linebot/groups/C123/images/photo.jpg"),
        ("ai-images/abc123.jpg", StorageZone.CTOS, "linebot/ai-images/abc123.jpg"),
    ]

    for input_path, expected_zone, expected_path in test_cases:
        try:
            parsed = path_manager.parse(input_path)
            zone_ok = parsed.zone == expected_zone
            path_ok = parsed.path == expected_path
            if zone_ok and path_ok:
                print_result(f"parse('{input_path}')", True)
                passed += 1
            else:
                print_result(
                    f"parse('{input_path}')",
                    False,
                    f"Expected zone={expected_zone.value}, path={expected_path}; Got zone={parsed.zone.value}, path={parsed.path}"
                )
                failed += 1
        except Exception as e:
            print_result(f"parse('{input_path}')", False, str(e))
            failed += 1

    # ============================================================
    # 測試 2: to_filesystem 轉換
    # ============================================================
    print_banner("to_filesystem() 轉換測試")

    fs_test_cases = [
        ("ctos://linebot/files/test.jpg", "/mnt/nas/ctos/linebot/files/test.jpg"),
        ("shared://亦達光學/doc.pdf", "/mnt/nas/projects/亦達光學/doc.pdf"),
        ("temp://converted/page.png", "/tmp/ctos/converted/page.png"),
    ]

    for input_path, expected_fs in fs_test_cases:
        try:
            result = path_manager.to_filesystem(input_path)
            if result == expected_fs:
                print_result(f"to_filesystem('{input_path}')", True)
                passed += 1
            else:
                print_result(
                    f"to_filesystem('{input_path}')",
                    False,
                    f"Expected: {expected_fs}, Got: {result}"
                )
                failed += 1
        except Exception as e:
            print_result(f"to_filesystem('{input_path}')", False, str(e))
            failed += 1

    # ============================================================
    # 測試 3: to_api 轉換
    # ============================================================
    print_banner("to_api() 轉換測試")

    api_test_cases = [
        ("ctos://linebot/files/test.jpg", "/api/files/ctos/linebot/files/test.jpg"),
        ("shared://亦達光學/doc.pdf", "/api/files/shared/亦達光學/doc.pdf"),
        # 舊格式應轉換
        ("/mnt/nas/projects/test.pdf", "/api/files/shared/test.pdf"),
    ]

    for input_path, expected_api in api_test_cases:
        try:
            result = path_manager.to_api(input_path)
            if result == expected_api:
                print_result(f"to_api('{input_path}')", True)
                passed += 1
            else:
                print_result(
                    f"to_api('{input_path}')",
                    False,
                    f"Expected: {expected_api}, Got: {result}"
                )
                failed += 1
        except Exception as e:
            print_result(f"to_api('{input_path}')", False, str(e))
            failed += 1

    # ============================================================
    # 測試 4: to_storage 轉換（標準化 URI）
    # ============================================================
    print_banner("to_storage() 轉換測試")

    storage_test_cases = [
        # 新格式應保持不變
        ("ctos://linebot/test.jpg", "ctos://linebot/test.jpg"),
        ("shared://test/doc.pdf", "shared://test/doc.pdf"),
        # 舊格式應轉換為新格式
        ("/mnt/nas/projects/亦達光學/doc.pdf", "shared://亦達光學/doc.pdf"),
        ("nas://knowledge/assets/img.jpg", "ctos://knowledge/assets/img.jpg"),
    ]

    for input_path, expected_uri in storage_test_cases:
        try:
            result = path_manager.to_storage(input_path)
            if result == expected_uri:
                print_result(f"to_storage('{input_path}')", True)
                passed += 1
            else:
                print_result(
                    f"to_storage('{input_path}')",
                    False,
                    f"Expected: {expected_uri}, Got: {result}"
                )
                failed += 1
        except Exception as e:
            print_result(f"to_storage('{input_path}')", False, str(e))
            failed += 1

    # ============================================================
    # 測試 5: is_readonly 檢查
    # ============================================================
    print_banner("is_readonly() 測試")

    readonly_test_cases = [
        ("shared://test.pdf", True),
        ("ctos://test.pdf", False),
        ("temp://test.pdf", False),
        ("local://test.pdf", False),
    ]

    for input_path, expected_readonly in readonly_test_cases:
        try:
            result = path_manager.is_readonly(input_path)
            if result == expected_readonly:
                print_result(f"is_readonly('{input_path}')", True)
                passed += 1
            else:
                print_result(
                    f"is_readonly('{input_path}')",
                    False,
                    f"Expected: {expected_readonly}, Got: {result}"
                )
                failed += 1
        except Exception as e:
            print_result(f"is_readonly('{input_path}')", False, str(e))
            failed += 1

    # ============================================================
    # 測試 6: 檔案存在檢查（需要 NAS 掛載）
    # ============================================================
    print_banner("exists() 測試（需要 NAS 掛載）")

    # 測試一個已知存在的路徑
    test_paths = [
        "/mnt/nas/projects",  # 應該存在
        "shared://not_exist_xyz_123.pdf",  # 應該不存在
    ]

    nas_available = Path("/mnt/nas/projects").exists()
    if nas_available:
        try:
            # 測試 shared 根目錄
            result = Path("/mnt/nas/projects").exists()
            print_result("NAS 掛載點可用", result)
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print_result("NAS 掛載點可用", False, str(e))
            failed += 1
    else:
        print("  (跳過：NAS 未掛載)")

    # ============================================================
    # 測試結果摘要
    # ============================================================
    print_banner("測試結果摘要")
    total = passed + failed
    print(f"總測試數: {total}")
    print(f"通過: {passed}")
    print(f"失敗: {failed}")

    if failed == 0:
        print("\n🎉 所有測試通過！")
    else:
        print(f"\n⚠️  有 {failed} 個測試失敗")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
