"""多平台綁定測試

注意：多租戶功能已移除，此測試中的 tenant_id 相關測試已停用。
待完全移除多租戶後需要重構此檔案。
"""

import pytest

pytestmark = pytest.mark.skip(reason="多租戶功能已移除，測試待重構")


class TestMultiPlatformBindingRemoved:
    """佔位測試類別 - 多平台綁定測試需要重構以移除 tenant_id"""

    def test_placeholder(self):
        """佔位測試"""
        pass
