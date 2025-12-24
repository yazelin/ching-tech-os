"""前端權限過濾功能 E2E 測試

使用 Playwright 測試：
- 桌面圖示根據權限過濾
- 管理員可看到所有應用程式
- 使用者管理分頁只有管理員可見
- 知識庫 scope 標記顯示

執行前需先啟動後端服務：
    uv run uvicorn ching_tech_os.main:app --reload

執行測試：
    uv run python -m pytest tests/test_frontend_permissions.py -v

注意：這些測試需要實際的後端服務和資料庫
"""

import os
import socket
import pytest
from playwright.sync_api import sync_playwright, Page, expect

# 測試環境設定
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")


def is_server_running() -> bool:
    """檢查後端服務是否在運行"""
    try:
        # 解析 URL 取得 host 和 port
        from urllib.parse import urlparse
        parsed = urlparse(BASE_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8000

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# 跳過條件：伺服器未運行
skip_server_not_running = pytest.mark.skipif(
    not is_server_running(),
    reason=f"後端服務未運行於 {BASE_URL}，請先啟動：uv run uvicorn ching_tech_os.main:app"
)

# 測試帳號（需要在資料庫中存在）
ADMIN_USERNAME = os.environ.get("TEST_ADMIN_USERNAME", "yazelin")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "")
USER_USERNAME = os.environ.get("TEST_USER_USERNAME", "")
USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "")


# 分開的跳過條件
skip_no_admin = pytest.mark.skipif(
    not ADMIN_PASSWORD,
    reason="需要設定 TEST_ADMIN_PASSWORD 環境變數"
)

skip_no_user = pytest.mark.skipif(
    not USER_PASSWORD or not USER_USERNAME,
    reason="需要設定 TEST_USER_USERNAME 和 TEST_USER_PASSWORD 環境變數"
)


def login(page: Page, username: str, password: str) -> bool:
    """登入並返回是否成功"""
    page.goto(f"{BASE_URL}/login.html")
    page.wait_for_load_state("networkidle")

    # 填寫登入表單
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[type='submit']")

    # 等待頁面跳轉（可能是 / 或 /index.html）
    try:
        # 等待不再是登入頁面
        page.wait_for_function(
            "!window.location.pathname.includes('login')",
            timeout=15000
        )
        # 確認有桌面元素（表示登入成功）
        page.wait_for_selector(".desktop-icon, .desktop", timeout=10000)
        return True
    except Exception:
        return False


# ============================================================
# 桌面圖示權限測試
# ============================================================

@skip_server_not_running
class TestDesktopIconPermissions:
    """桌面圖示權限過濾測試"""

    @skip_no_admin
    def test_admin_can_see_all_apps(self):
        """管理員可以看到所有應用程式"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            assert login(page, ADMIN_USERNAME, ADMIN_PASSWORD), "管理員登入失敗"

            # 等待桌面載入
            page.wait_for_selector(".desktop-icon", timeout=10000)

            # 管理員應該能看到終端機和程式編輯器
            terminal_icon = page.locator(".desktop-icon[data-app-id='terminal']")
            code_editor_icon = page.locator(".desktop-icon[data-app-id='code-editor']")

            expect(terminal_icon).to_be_visible()
            expect(code_editor_icon).to_be_visible()

            browser.close()

    @skip_no_user
    def test_normal_user_cannot_see_restricted_apps(self):
        """一般使用者看不到受限制的應用程式"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            assert login(page, USER_USERNAME, USER_PASSWORD), "使用者登入失敗"

            # 等待桌面載入
            page.wait_for_selector(".desktop-icon", timeout=10000)

            # 一般使用者預設看不到終端機和程式編輯器
            terminal_icon = page.locator(".desktop-icon[data-app-id='terminal']")
            code_editor_icon = page.locator(".desktop-icon[data-app-id='code-editor']")

            expect(terminal_icon).not_to_be_visible()
            expect(code_editor_icon).not_to_be_visible()

            # 但可以看到檔案管理等預設開放的應用程式
            file_manager_icon = page.locator(".desktop-icon[data-app-id='file-manager']")
            expect(file_manager_icon).to_be_visible()

            browser.close()


# ============================================================
# 設定分頁權限測試
# ============================================================

@skip_server_not_running
class TestSettingsPermissions:
    """系統設定權限測試"""

    @skip_no_admin
    def test_admin_can_see_user_management_tab(self):
        """管理員可以看到使用者管理分頁"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            assert login(page, ADMIN_USERNAME, ADMIN_PASSWORD), "管理員登入失敗"

            # 等待桌面載入後開啟設定
            page.wait_for_selector(".desktop-icon", timeout=10000)
            page.dblclick(".desktop-icon[data-app-id='settings']")

            # 等待設定視窗開啟
            page.wait_for_selector(".window-content", timeout=10000)
            page.wait_for_selector(".settings-nav", timeout=5000)

            # 管理員應該能看到使用者管理分頁
            user_management_tab = page.locator("[data-section='users']")
            expect(user_management_tab).to_be_visible()

            browser.close()

    @skip_no_user
    def test_normal_user_cannot_see_user_management_tab(self):
        """一般使用者看不到使用者管理分頁"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            assert login(page, USER_USERNAME, USER_PASSWORD), "使用者登入失敗"

            # 等待桌面載入後開啟設定
            page.wait_for_selector(".desktop-icon", timeout=10000)
            page.dblclick(".desktop-icon[data-app-id='settings']")

            # 等待設定視窗開啟
            page.wait_for_selector(".window-content", timeout=10000)
            page.wait_for_selector(".settings-nav", timeout=5000)

            # 一般使用者看不到使用者管理分頁
            user_management_tab = page.locator("[data-section='users']")
            expect(user_management_tab).not_to_be_visible()

            browser.close()


# ============================================================
# 知識庫 UI 測試
# ============================================================

@skip_server_not_running
class TestKnowledgeBaseUI:
    """知識庫 UI 測試"""

    @skip_no_admin
    def test_knowledge_list_shows_scope_badge(self):
        """知識列表顯示 scope 標記"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            assert login(page, ADMIN_USERNAME, ADMIN_PASSWORD), "登入失敗"

            # 開啟知識庫
            page.wait_for_selector(".desktop-icon", timeout=10000)
            page.dblclick(".desktop-icon[data-app-id='knowledge-base']")

            # 等待知識庫載入
            page.wait_for_selector(".window-content", timeout=10000)
            page.wait_for_selector(".kb-list", timeout=10000)

            # 檢查是否有 scope 標記（全域或個人）
            scope_badges = page.locator(".kb-scope-badge")

            # 只要有任何知識項目，就應該有 scope 標記
            knowledge_items = page.locator(".kb-list-item")
            if knowledge_items.count() > 0:
                expect(scope_badges.first).to_be_visible()

            browser.close()

    @skip_no_admin
    def test_new_knowledge_has_scope_selector(self):
        """新增知識時可選擇 scope"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            assert login(page, ADMIN_USERNAME, ADMIN_PASSWORD), "登入失敗"

            # 開啟知識庫
            page.wait_for_selector(".desktop-icon", timeout=10000)
            page.dblclick(".desktop-icon[data-app-id='knowledge-base']")

            # 等待知識庫載入
            page.wait_for_selector(".window-content", timeout=10000)
            page.wait_for_selector(".kb-list", timeout=10000)

            # 點擊新增按鈕
            add_button = page.locator("#kbBtnNew")
            add_button.click()

            # 等待編輯表單
            page.wait_for_selector(".kb-editor", timeout=5000)

            # 檢查是否有 scope 選擇器
            scope_selector = page.locator("#kbEditorScope")
            expect(scope_selector).to_be_visible()

            browser.close()


# ============================================================
# 無需登入的基本測試
# ============================================================

@skip_server_not_running
class TestBasicFrontend:
    """基本前端測試（無需登入）"""

    def test_login_page_loads(self):
        """登入頁面可正常載入"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            response = page.goto(f"{BASE_URL}/login.html")

            # 檢查頁面載入成功
            assert response is not None
            assert response.status == 200

            # 檢查登入表單存在
            username_field = page.locator("#username")
            password_field = page.locator("#password")
            submit_button = page.locator("button[type='submit']")

            expect(username_field).to_be_visible()
            expect(password_field).to_be_visible()
            expect(submit_button).to_be_visible()

            browser.close()

    def test_unauthenticated_redirect_to_login(self):
        """未登入時應導向登入頁面或顯示登入表單"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 嘗試直接存取主頁面
            page.goto(f"{BASE_URL}/")

            # 等待 JavaScript 執行重導向或顯示登入表單
            page.wait_for_timeout(3000)

            # 應該被導向到登入頁面，或者頁面上有登入表單
            current_url = page.url
            has_login_form = page.locator("#username").count() > 0

            assert "login" in current_url or has_login_form, \
                f"應導向登入頁面或顯示登入表單，但目前 URL: {current_url}"

            browser.close()
