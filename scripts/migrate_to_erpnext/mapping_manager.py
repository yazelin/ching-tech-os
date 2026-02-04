#!/usr/bin/env python3
"""
ID 映射表管理
統一管理 CTOS → ERPNext 的 ID 映射關係
"""
import json
from datetime import datetime
from pathlib import Path

# 預設映射表儲存路徑
DEFAULT_MAPPING_FILE = Path(__file__).parent / "id_mapping.json"


class MappingManager:
    """ID 映射表管理器"""

    def __init__(self, file_path: str | Path = None):
        self.file_path = Path(file_path) if file_path else DEFAULT_MAPPING_FILE
        self.mapping = self._load()

    def _load(self) -> dict:
        """載入映射表"""
        if self.file_path.exists():
            with open(self.file_path) as f:
                return json.load(f)
        return self._create_empty()

    def _create_empty(self) -> dict:
        """建立空的映射表結構"""
        return {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "version": "1.0",
            },
            "vendors": {},      # CTOS vendor_id → ERPNext Supplier name
            "items": {},        # CTOS item_id → ERPNext Item code
            "projects": {},     # CTOS project_id → ERPNext Project name
            "milestones": {},   # CTOS milestone_id → ERPNext Task name
            "meetings": {},     # CTOS meeting_id → ERPNext Event name
            "items_with_stock": [],  # 需要建立期初庫存的物料清單
        }

    def save(self) -> None:
        """儲存映射表"""
        self.mapping["metadata"]["updated_at"] = datetime.now().isoformat()
        with open(self.file_path, "w") as f:
            json.dump(self.mapping, f, indent=2, ensure_ascii=False)
        print(f"✓ 映射表已儲存: {self.file_path}")

    def add_vendor(self, ctos_id: str, erpnext_name: str) -> None:
        """新增廠商映射"""
        self.mapping["vendors"][str(ctos_id)] = erpnext_name

    def add_item(self, ctos_id: str, erpnext_code: str) -> None:
        """新增物料映射"""
        self.mapping["items"][str(ctos_id)] = erpnext_code

    def add_project(self, ctos_id: str, erpnext_name: str) -> None:
        """新增專案映射"""
        self.mapping["projects"][str(ctos_id)] = erpnext_name

    def add_milestone(self, ctos_id: str, erpnext_task: str) -> None:
        """新增里程碑映射"""
        self.mapping["milestones"][str(ctos_id)] = erpnext_task

    def add_meeting(self, ctos_id: str, erpnext_event: str) -> None:
        """新增會議映射"""
        self.mapping["meetings"][str(ctos_id)] = erpnext_event

    def add_item_with_stock(self, item_code: str, qty: float, name: str) -> None:
        """新增需要建立期初庫存的物料"""
        self.mapping["items_with_stock"].append({
            "item_code": item_code,
            "qty": qty,
            "name": name,
        })

    def get_vendor(self, ctos_id: str) -> str | None:
        """取得廠商 ERPNext 名稱"""
        return self.mapping["vendors"].get(str(ctos_id))

    def get_item(self, ctos_id: str) -> str | None:
        """取得物料 ERPNext 代碼"""
        return self.mapping["items"].get(str(ctos_id))

    def get_project(self, ctos_id: str) -> str | None:
        """取得專案 ERPNext 名稱"""
        return self.mapping["projects"].get(str(ctos_id))

    def get_vendors(self) -> dict:
        """取得所有廠商映射"""
        return self.mapping["vendors"]

    def get_items(self) -> dict:
        """取得所有物料映射"""
        return self.mapping["items"]

    def get_projects(self) -> dict:
        """取得所有專案映射"""
        return self.mapping["projects"]

    def get_items_with_stock(self) -> list[dict]:
        """取得需要建立期初庫存的物料清單"""
        return self.mapping["items_with_stock"]

    def merge(self, other_mapping: dict) -> None:
        """合併其他映射表"""
        for key in ["vendors", "items", "projects", "milestones", "meetings"]:
            if key in other_mapping:
                self.mapping[key].update(other_mapping[key])

        if "items_with_stock" in other_mapping:
            existing_codes = {item["item_code"] for item in self.mapping["items_with_stock"]}
            for item in other_mapping["items_with_stock"]:
                if item["item_code"] not in existing_codes:
                    self.mapping["items_with_stock"].append(item)

    def summary(self) -> str:
        """產生映射表摘要"""
        lines = [
            "=" * 50,
            "ID 映射表摘要",
            "=" * 50,
            f"檔案: {self.file_path}",
            f"更新時間: {self.mapping['metadata']['updated_at']}",
            "",
            f"廠商: {len(self.mapping['vendors'])} 筆",
            f"物料: {len(self.mapping['items'])} 筆",
            f"專案: {len(self.mapping['projects'])} 筆",
            f"里程碑: {len(self.mapping['milestones'])} 筆",
            f"會議: {len(self.mapping['meetings'])} 筆",
            f"待建期初庫存: {len(self.mapping['items_with_stock'])} 筆",
        ]
        return "\n".join(lines)


def main():
    """CLI 工具"""
    import argparse

    parser = argparse.ArgumentParser(description="ID 映射表管理工具")
    parser.add_argument("--file", type=str, help="映射表檔案路徑")
    parser.add_argument("--summary", action="store_true", help="顯示映射表摘要")
    parser.add_argument("--export", type=str, help="匯出映射表到指定路徑")
    parser.add_argument("--merge", type=str, help="合併另一個映射表檔案")
    args = parser.parse_args()

    manager = MappingManager(args.file)

    if args.summary:
        print(manager.summary())

    if args.merge:
        with open(args.merge) as f:
            other = json.load(f)
        manager.merge(other)
        manager.save()
        print(f"已合併: {args.merge}")

    if args.export:
        with open(args.export, "w") as f:
            json.dump(manager.mapping, f, indent=2, ensure_ascii=False)
        print(f"已匯出: {args.export}")


if __name__ == "__main__":
    main()
