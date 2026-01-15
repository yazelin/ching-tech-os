#!/usr/bin/env python3
"""Files API 端對端測試

這個腳本測試 /api/files/{zone}/{path} API 在真實環境中的運作。
需要後端服務運行中才能執行。

執行方式：
    cd backend && uv run python tests/e2e/test_files_api_e2e.py

前置條件：
    1. 後端服務運行中 (localhost:8000)
    2. 有效的認證 token（透過環境變數或設定檔）
    3. NAS 掛載點可用
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from urllib.parse import quote

# 嘗試導入 httpx，如果沒有則使用 urllib
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_HTTPX = False


# 設定
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")  # 需要提供有效 token

# 測試用的檔案（需要實際存在）
TEST_FILES = {
    "shared": "在案資料分享",  # 一個已知存在的目錄
    "ctos": "linebot",  # CTOS 區的目錄
}


def test_banner(name: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print('='*60)


def test_result(name: str, passed: bool, detail: str = ""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {name}")
    if detail:
        print(f"       {detail}")


def make_request(method: str, url: str, headers: dict = None) -> tuple:
    """發送 HTTP 請求，回傳 (status_code, response_body)"""
    if HAS_HTTPX:
        with httpx.Client() as client:
            response = client.request(method, url, headers=headers)
            return response.status_code, response.text
    else:
        req = urllib.request.Request(url, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()


def run_tests():
    """執行所有 Files API 端對端測試"""
    passed = 0
    failed = 0

    # 檢查後端是否運行
    test_banner("前置檢查")

    try:
        status, body = make_request("GET", f"{API_BASE}/api/health")
        if status == 200:
            test_result("後端服務運行中", True)
            passed += 1
        else:
            test_result("後端服務運行中", False, f"Status: {status}")
            print("\n⚠️  後端服務未運行，無法執行 API 測試")
            return False
    except Exception as e:
        test_result("後端服務運行中", False, str(e))
        print("\n⚠️  無法連接後端服務，無法執行 API 測試")
        return False

    # ============================================================
    # 測試 1: 無效 zone 應回傳 400
    # ============================================================
    test_banner("錯誤處理測試")

    if AUTH_TOKEN:
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

        # 無效 zone
        try:
            status, body = make_request(
                "GET",
                f"{API_BASE}/api/files/invalid_zone/test.txt",
                headers
            )
            if status == 400:
                test_result("無效 zone 回傳 400", True)
                passed += 1
            else:
                test_result("無效 zone 回傳 400", False, f"Got status {status}")
                failed += 1
        except Exception as e:
            test_result("無效 zone 回傳 400", False, str(e))
            failed += 1

        # 路徑穿越
        try:
            status, body = make_request(
                "GET",
                f"{API_BASE}/api/files/shared/../etc/passwd",
                headers
            )
            if status == 400:
                test_result("路徑穿越被阻擋 (..)", True)
                passed += 1
            else:
                test_result("路徑穿越被阻擋 (..)", False, f"Got status {status}")
                failed += 1
        except Exception as e:
            test_result("路徑穿越被阻擋 (..)", False, str(e))
            failed += 1
    else:
        print("  (跳過：未提供 AUTH_TOKEN)")

    # ============================================================
    # 測試 2: 未授權請求應回傳 401
    # ============================================================
    test_banner("認證測試")

    try:
        status, body = make_request(
            "GET",
            f"{API_BASE}/api/files/shared/test.txt"
            # 不帶 Authorization header
        )
        if status == 401:
            test_result("未授權請求回傳 401", True)
            passed += 1
        else:
            test_result("未授權請求回傳 401", False, f"Got status {status}")
            failed += 1
    except Exception as e:
        test_result("未授權請求回傳 401", False, str(e))
        failed += 1

    # ============================================================
    # 測試 3: 各 Zone 有效性（需要 token）
    # ============================================================
    if AUTH_TOKEN:
        test_banner("Zone 有效性測試")

        for zone in ["ctos", "shared", "temp", "local", "nas"]:
            try:
                # 請求一個不存在的檔案，應該得到 404（而不是 400）
                status, body = make_request(
                    "GET",
                    f"{API_BASE}/api/files/{zone}/nonexistent_xyz_123.txt",
                    headers
                )
                # 404 表示 zone 有效但檔案不存在，這是正確的
                if status == 404:
                    test_result(f"Zone '{zone}' 有效", True)
                    passed += 1
                elif status == 400:
                    test_result(f"Zone '{zone}' 有效", False, "Zone 被拒絕")
                    failed += 1
                else:
                    test_result(f"Zone '{zone}' 有效", True, f"Status: {status}")
                    passed += 1
            except Exception as e:
                test_result(f"Zone '{zone}' 有效", False, str(e))
                failed += 1

    # ============================================================
    # 測試 4: 讀取實際檔案（需要 token 和 NAS）
    # ============================================================
    if AUTH_TOKEN:
        test_banner("檔案讀取測試")

        # 檢查 NAS 是否可用
        nas_path = Path("/mnt/nas/projects")
        if nas_path.exists():
            # 找一個實際存在的檔案
            test_files = list(nas_path.glob("**/*.txt"))[:1]
            if test_files:
                rel_path = test_files[0].relative_to(nas_path)
                encoded_path = quote(str(rel_path), safe="/")
                try:
                    status, body = make_request(
                        "GET",
                        f"{API_BASE}/api/files/shared/{encoded_path}",
                        headers
                    )
                    if status == 200:
                        test_result(f"讀取 shared://{rel_path}", True)
                        passed += 1
                    else:
                        test_result(f"讀取 shared://{rel_path}", False, f"Status: {status}")
                        failed += 1
                except Exception as e:
                    test_result(f"讀取 shared://{rel_path}", False, str(e))
                    failed += 1
            else:
                print("  (跳過：找不到測試用的 .txt 檔案)")
        else:
            print("  (跳過：NAS 未掛載)")

    # ============================================================
    # 測試結果摘要
    # ============================================================
    test_banner("測試結果摘要")
    total = passed + failed
    print(f"總測試數: {total}")
    print(f"通過: {passed}")
    print(f"失敗: {failed}")

    if not AUTH_TOKEN:
        print("\n💡 提示：設定 AUTH_TOKEN 環境變數以執行完整測試")
        print("   export AUTH_TOKEN='your_token_here'")

    if failed == 0:
        print("\n🎉 所有測試通過！")
    else:
        print(f"\n⚠️  有 {failed} 個測試失敗")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
