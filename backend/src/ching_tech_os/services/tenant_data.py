"""租戶資料匯出/匯入服務

提供租戶資料的備份與還原功能。
"""

import io
import json
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from uuid import UUID
from typing import Any

from ..config import settings
from ..database import get_connection
from ..models.tenant import TenantExportRequest


class TenantDataError(Exception):
    """租戶資料操作錯誤"""
    pass


class TenantExportService:
    """租戶資料匯出服務"""

    # 需要匯出的資料表（按依賴順序排列）
    EXPORT_TABLES = [
        # 基礎資料（無外鍵依賴）
        "users",
        "vendors",
        "inventory_items",
        "ai_agents",
        "ai_prompts",
        "line_groups",
        "line_users",
        # 有外鍵依賴的資料
        "projects",
        "project_members",
        "project_meetings",
        "project_milestones",
        "project_attachments",
        "project_links",
        "project_delivery_schedules",
        "inventory_transactions",
        "line_messages",
        "ai_chats",
        "public_share_links",
        "tenant_admins",
    ]

    # AI logs 因資料量大，預設不匯出
    OPTIONAL_TABLES = [
        "ai_logs",
    ]

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self.export_dir: Path | None = None

    async def export_to_zip(self, request: TenantExportRequest) -> tuple[bytes, dict]:
        """匯出租戶資料為 ZIP 檔案

        Args:
            request: 匯出請求參數

        Returns:
            (ZIP 檔案內容, 匯出摘要)
        """
        summary = {
            "tenant_id": str(self.tenant_id),
            "exported_at": datetime.now().isoformat(),
            "tables": {},
            "files_included": request.include_files,
            "ai_logs_included": request.include_ai_logs,
        }

        # 建立記憶體 ZIP
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 匯出資料庫資料
            tables_to_export = self.EXPORT_TABLES.copy()
            if request.include_ai_logs:
                tables_to_export.extend(self.OPTIONAL_TABLES)

            for table_name in tables_to_export:
                try:
                    data = await self._export_table(table_name)
                    if data:
                        json_content = json.dumps(data, default=str, ensure_ascii=False, indent=2)
                        zf.writestr(f"data/{table_name}.json", json_content.encode("utf-8"))
                        summary["tables"][table_name] = len(data)
                except Exception as e:
                    # 某些表可能不存在或查詢失敗，記錄但繼續
                    summary["tables"][table_name] = f"error: {str(e)}"

            # 匯出知識庫檔案（如果請求）
            if request.include_files:
                files_count = await self._export_files(zf)
                summary["files_count"] = files_count

            # 寫入匯出摘要
            zf.writestr("manifest.json", json.dumps(summary, default=str, ensure_ascii=False, indent=2).encode("utf-8"))

        zip_buffer.seek(0)
        return zip_buffer.getvalue(), summary

    async def _export_table(self, table_name: str) -> list[dict]:
        """匯出單一資料表

        Args:
            table_name: 資料表名稱

        Returns:
            資料列表
        """
        async with get_connection() as conn:
            # 檢查表是否存在 tenant_id 欄位
            column_check = await conn.fetchval("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = $1 AND column_name = 'tenant_id'
            """, table_name)

            if column_check:
                # 有 tenant_id 欄位，只匯出該租戶的資料
                rows = await conn.fetch(f"""
                    SELECT * FROM {table_name}
                    WHERE tenant_id = $1
                """, self.tenant_id)
            else:
                # 沒有 tenant_id 欄位（例如 tenant_admins），根據關聯查詢
                if table_name == "tenant_admins":
                    rows = await conn.fetch("""
                        SELECT * FROM tenant_admins
                        WHERE tenant_id = $1
                    """, self.tenant_id)
                else:
                    return []

            # 轉換為 dict 列表
            return [dict(row) for row in rows]

    async def _export_files(self, zf: zipfile.ZipFile) -> int:
        """匯出租戶檔案到 ZIP

        Args:
            zf: ZIP 檔案物件

        Returns:
            匯出的檔案數量
        """
        count = 0

        # 取得租戶檔案目錄
        tenant_dir = Path(settings.tenant_data_path(str(self.tenant_id)))
        if not tenant_dir.exists():
            return 0

        # 遍歷並加入檔案
        for file_path in tenant_dir.rglob("*"):
            if file_path.is_file():
                # 計算相對路徑
                relative_path = file_path.relative_to(tenant_dir)
                zf.write(file_path, f"files/{relative_path}")
                count += 1

        return count


class TenantImportService:
    """租戶資料匯入服務"""

    # 匯入順序（需考慮外鍵依賴）
    IMPORT_ORDER = [
        # 1. 基礎資料（無外鍵依賴）
        "users",
        "vendors",
        "inventory_items",
        "ai_agents",
        "ai_prompts",
        "line_groups",
        "line_users",
        # 2. 有外鍵依賴的資料
        "projects",
        "project_members",
        "project_meetings",
        "project_milestones",
        "project_attachments",
        "project_links",
        "project_delivery_schedules",
        "inventory_transactions",
        "line_messages",
        "ai_chats",
        "public_share_links",
        "tenant_admins",
        # 3. 可選資料
        "ai_logs",
    ]

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self.id_mapping: dict[str, dict[str, str]] = {}  # table -> {old_id: new_id}

    async def import_from_zip(
        self,
        zip_content: bytes,
        merge_mode: str = "replace",
    ) -> dict:
        """從 ZIP 匯入租戶資料

        Args:
            zip_content: ZIP 檔案內容
            merge_mode: 合併模式 ("replace" 或 "merge")

        Returns:
            匯入摘要
        """
        summary = {
            "tenant_id": str(self.tenant_id),
            "imported_at": datetime.now().isoformat(),
            "merge_mode": merge_mode,
            "tables": {},
            "files_imported": 0,
            "errors": [],
        }

        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
            # 讀取 manifest
            try:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                summary["source_tenant_id"] = manifest.get("tenant_id")
                summary["source_exported_at"] = manifest.get("exported_at")
            except Exception:
                pass

            # 如果是取代模式，先清除現有資料
            if merge_mode == "replace":
                await self._clear_tenant_data()

            # 按順序匯入資料表
            for table_name in self.IMPORT_ORDER:
                try:
                    data_path = f"data/{table_name}.json"
                    if data_path in zf.namelist():
                        data = json.loads(zf.read(data_path).decode("utf-8"))
                        count = await self._import_table(table_name, data, merge_mode)
                        summary["tables"][table_name] = count
                except Exception as e:
                    error_msg = f"{table_name}: {str(e)}"
                    summary["errors"].append(error_msg)
                    summary["tables"][table_name] = f"error: {str(e)}"

            # 匯入檔案
            files_count = await self._import_files(zf)
            summary["files_imported"] = files_count

        return summary

    async def _clear_tenant_data(self) -> None:
        """清除租戶現有資料"""
        async with get_connection() as conn:
            # 按反向順序刪除（先刪有外鍵依賴的）
            for table_name in reversed(self.IMPORT_ORDER):
                try:
                    # 檢查表是否存在
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = $1
                        )
                    """, table_name)

                    if table_exists:
                        # 檢查是否有 tenant_id 欄位
                        has_tenant_id = await conn.fetchval("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = $1 AND column_name = 'tenant_id'
                        """, table_name)

                        if has_tenant_id:
                            await conn.execute(f"""
                                DELETE FROM {table_name} WHERE tenant_id = $1
                            """, self.tenant_id)
                except Exception:
                    # 忽略刪除錯誤
                    pass

    async def _import_table(
        self,
        table_name: str,
        data: list[dict],
        merge_mode: str,
    ) -> int:
        """匯入單一資料表

        Args:
            table_name: 資料表名稱
            data: 資料列表
            merge_mode: 合併模式

        Returns:
            匯入的記錄數
        """
        if not data:
            return 0

        async with get_connection() as conn:
            count = 0

            for row in data:
                try:
                    # 更新 tenant_id 為目標租戶
                    if "tenant_id" in row:
                        row["tenant_id"] = self.tenant_id

                    # 處理 ID 映射（某些表的 ID 可能需要重新生成）
                    old_id = row.get("id")

                    # 動態建立 INSERT 語句
                    columns = list(row.keys())
                    placeholders = [f"${i+1}" for i in range(len(columns))]
                    values = [self._convert_value(row[col]) for col in columns]

                    # 如果是合併模式且記錄已存在，跳過
                    if merge_mode == "merge" and old_id:
                        exists = await conn.fetchval(f"""
                            SELECT id FROM {table_name}
                            WHERE id = $1 AND tenant_id = $2
                        """, self._convert_value(old_id), self.tenant_id)
                        if exists:
                            continue

                    await conn.execute(f"""
                        INSERT INTO {table_name} ({', '.join(columns)})
                        VALUES ({', '.join(placeholders)})
                        ON CONFLICT DO NOTHING
                    """, *values)
                    count += 1

                except Exception:
                    # 忽略單筆插入錯誤，繼續處理
                    pass

            return count

    def _convert_value(self, value: Any) -> Any:
        """轉換值為適合資料庫的格式"""
        if value is None:
            return None
        if isinstance(value, str):
            # 嘗試轉換 UUID 字串
            try:
                return UUID(value)
            except (ValueError, TypeError):
                pass
            # 嘗試轉換日期時間
            for fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    pass
        return value

    async def _import_files(self, zf: zipfile.ZipFile) -> int:
        """從 ZIP 匯入檔案

        Args:
            zf: ZIP 檔案物件

        Returns:
            匯入的檔案數量
        """
        count = 0
        tenant_dir = Path(settings.tenant_data_path(str(self.tenant_id)))

        for name in zf.namelist():
            if name.startswith("files/") and not name.endswith("/"):
                # 取得相對路徑
                relative_path = name[6:]  # 移除 "files/" 前綴
                target_path = tenant_dir / relative_path

                # 確保目標目錄存在
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # 解壓縮檔案
                with zf.open(name) as src:
                    with open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                count += 1

        return count


class TenantMigrationService:
    """租戶遷移服務

    用於跨實例的租戶資料遷移（試用轉正式等場景）。
    """

    def __init__(self, source_tenant_id: UUID, target_tenant_id: UUID):
        self.source_tenant_id = source_tenant_id
        self.target_tenant_id = target_tenant_id

    async def migrate(
        self,
        include_files: bool = True,
        include_ai_logs: bool = False,
    ) -> dict:
        """執行租戶遷移

        Args:
            include_files: 是否遷移檔案
            include_ai_logs: 是否遷移 AI 日誌

        Returns:
            遷移摘要
        """
        # 1. 匯出來源租戶資料
        export_service = TenantExportService(self.source_tenant_id)
        export_request = TenantExportRequest(
            include_files=include_files,
            include_ai_logs=include_ai_logs,
        )
        zip_content, export_summary = await export_service.export_to_zip(export_request)

        # 2. 匯入到目標租戶
        import_service = TenantImportService(self.target_tenant_id)
        import_summary = await import_service.import_from_zip(zip_content, merge_mode="replace")

        return {
            "source_tenant_id": str(self.source_tenant_id),
            "target_tenant_id": str(self.target_tenant_id),
            "export_summary": export_summary,
            "import_summary": import_summary,
        }


class TenantDataValidator:
    """租戶資料驗證工具

    用於驗證匯入/遷移後資料的完整性。
    """

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id

    async def validate(self) -> dict:
        """驗證租戶資料完整性

        Returns:
            驗證結果
        """
        results = {
            "tenant_id": str(self.tenant_id),
            "validated_at": datetime.now().isoformat(),
            "checks": {},
            "errors": [],
            "warnings": [],
        }

        async with get_connection() as conn:
            # 1. 檢查租戶是否存在
            tenant = await conn.fetchrow("""
                SELECT id, code, name FROM tenants WHERE id = $1
            """, self.tenant_id)

            if not tenant:
                results["errors"].append("租戶不存在")
                return results

            results["tenant_code"] = tenant["code"]
            results["tenant_name"] = tenant["name"]

            # 2. 檢查各表資料數量
            tables_to_check = [
                "users",
                "projects",
                "vendors",
                "inventory_items",
            ]

            for table in tables_to_check:
                try:
                    count = await conn.fetchval(f"""
                        SELECT COUNT(*) FROM {table}
                        WHERE tenant_id = $1
                    """, self.tenant_id)
                    results["checks"][table] = {"count": count, "status": "ok"}
                except Exception as e:
                    results["checks"][table] = {"status": "error", "message": str(e)}

            # 3. 檢查外鍵完整性
            await self._check_foreign_keys(conn, results)

            # 4. 檢查檔案系統
            await self._check_files(results)

        return results

    async def _check_foreign_keys(self, conn, results: dict) -> None:
        """檢查外鍵完整性"""
        # 檢查 project_members 的 project_id
        orphan_members = await conn.fetchval("""
            SELECT COUNT(*) FROM project_members pm
            WHERE pm.tenant_id = $1
            AND NOT EXISTS (
                SELECT 1 FROM projects p
                WHERE p.id = pm.project_id AND p.tenant_id = $1
            )
        """, self.tenant_id)

        if orphan_members and orphan_members > 0:
            results["warnings"].append(f"發現 {orphan_members} 筆孤立的專案成員記錄")

        # 檢查 inventory_transactions 的 item_id
        orphan_transactions = await conn.fetchval("""
            SELECT COUNT(*) FROM inventory_transactions it
            WHERE it.tenant_id = $1
            AND NOT EXISTS (
                SELECT 1 FROM inventory_items i
                WHERE i.id = it.item_id AND i.tenant_id = $1
            )
        """, self.tenant_id)

        if orphan_transactions and orphan_transactions > 0:
            results["warnings"].append(f"發現 {orphan_transactions} 筆孤立的庫存交易記錄")

    async def _check_files(self, results: dict) -> None:
        """檢查檔案系統"""
        tenant_dir = Path(settings.tenant_data_path(str(self.tenant_id)))

        if tenant_dir.exists():
            # 計算檔案數量和大小
            file_count = sum(1 for _ in tenant_dir.rglob("*") if _.is_file())
            total_size = sum(f.stat().st_size for f in tenant_dir.rglob("*") if f.is_file())

            results["checks"]["files"] = {
                "status": "ok",
                "count": file_count,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
            }
        else:
            results["checks"]["files"] = {
                "status": "ok",
                "count": 0,
                "message": "檔案目錄不存在（可能是新租戶）",
            }


# === 便捷函數 ===


async def export_tenant_data(
    tenant_id: UUID | str,
    include_files: bool = True,
    include_ai_logs: bool = False,
) -> tuple[bytes, dict]:
    """匯出租戶資料

    Args:
        tenant_id: 租戶 UUID
        include_files: 是否包含檔案
        include_ai_logs: 是否包含 AI 日誌

    Returns:
        (ZIP 內容, 匯出摘要)
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    service = TenantExportService(tenant_id)
    request = TenantExportRequest(
        include_files=include_files,
        include_ai_logs=include_ai_logs,
    )
    return await service.export_to_zip(request)


async def import_tenant_data(
    tenant_id: UUID | str,
    zip_content: bytes,
    merge_mode: str = "replace",
) -> dict:
    """匯入租戶資料

    Args:
        tenant_id: 租戶 UUID
        zip_content: ZIP 檔案內容
        merge_mode: 合併模式

    Returns:
        匯入摘要
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    service = TenantImportService(tenant_id)
    return await service.import_from_zip(zip_content, merge_mode)


async def validate_tenant_data(tenant_id: UUID | str) -> dict:
    """驗證租戶資料完整性

    Args:
        tenant_id: 租戶 UUID

    Returns:
        驗證結果
    """
    if isinstance(tenant_id, str):
        tenant_id = UUID(tenant_id)

    validator = TenantDataValidator(tenant_id)
    return await validator.validate()


async def migrate_tenant(
    source_tenant_id: UUID | str,
    target_tenant_id: UUID | str,
    include_files: bool = True,
    include_ai_logs: bool = False,
) -> dict:
    """遷移租戶資料

    Args:
        source_tenant_id: 來源租戶 UUID
        target_tenant_id: 目標租戶 UUID
        include_files: 是否遷移檔案
        include_ai_logs: 是否遷移 AI 日誌

    Returns:
        遷移摘要
    """
    if isinstance(source_tenant_id, str):
        source_tenant_id = UUID(source_tenant_id)
    if isinstance(target_tenant_id, str):
        target_tenant_id = UUID(target_tenant_id)

    service = TenantMigrationService(source_tenant_id, target_tenant_id)
    return await service.migrate(
        include_files=include_files,
        include_ai_logs=include_ai_logs,
    )
