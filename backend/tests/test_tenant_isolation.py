"""租戶隔離單元測試

注意：多租戶功能已移除，此測試檔案已停用。
待完全移除多租戶後可刪除此檔案。
"""

import pytest

pytestmark = pytest.mark.skip(reason="多租戶功能已移除，測試待刪除")


class TestTenantIsolationRemoved:
    """佔位測試類別 - 所有租戶隔離測試已移除"""

    def test_placeholder(self):
        """佔位測試"""
        pass
