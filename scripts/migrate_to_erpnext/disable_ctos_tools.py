#!/usr/bin/env python3
"""
停用 CTOS MCP 工具
在遷移到 ERPNext 後，將相關工具標記為已停用
"""
import re
from pathlib import Path

MCP_SERVER_PATH = Path(__file__).parent.parent.parent / "backend/src/ching_tech_os/services/mcp_server.py"

# 要停用的工具列表（依類別分組）
DEPRECATED_TOOLS = {
    "專案管理": [
        "query_project",
        "create_project",
        "update_project",
        "add_project_member",
        "update_project_member",
        "get_project_members",
        "add_project_milestone",
        "update_milestone",
        "get_project_milestones",
        "add_project_meeting",
        "update_project_meeting",
        "get_project_meetings",
        "add_delivery_schedule",
        "update_delivery_schedule",
        "get_delivery_schedules",
        "add_project_link",
        "get_project_links",
        "update_project_link",
        "delete_project_link",
        "add_project_attachment",
        "get_project_attachments",
        "update_project_attachment",
        "delete_project_attachment",
    ],
    "廠商管理": [
        "query_vendors",
        "add_vendor",
        "update_vendor",
    ],
    "物料管理": [
        "query_inventory",
        "add_inventory_item",
        "update_inventory_item",
        "record_inventory_in",
        "record_inventory_out",
        "adjust_inventory",
        "query_project_inventory",
        "add_inventory_order",
        "update_inventory_order",
        "get_inventory_orders",
    ],
}

# ERPNext 對應工具指引
ERPNEXT_GUIDANCE = {
    "專案管理": """請使用 ERPNext MCP 工具操作：
- 專案查詢：mcp__erpnext__list_documents (doctype="Project")
- 專案詳情：mcp__erpnext__get_document (doctype="Project", name="專案名稱")
- 任務：mcp__erpnext__list_documents (doctype="Task")""",
    "廠商管理": """請使用 ERPNext MCP 工具操作：
- 廠商查詢：mcp__erpnext__list_documents (doctype="Supplier")
- 廠商詳情：mcp__erpnext__get_document (doctype="Supplier", name="廠商名稱")
- 新增廠商：mcp__erpnext__create_document (doctype="Supplier")""",
    "物料管理": """請使用 ERPNext MCP 工具操作：
- 物料查詢：mcp__erpnext__list_documents (doctype="Item")
- 庫存查詢：mcp__erpnext__get_stock_balance
- 入庫/出庫：mcp__erpnext__create_document (doctype="Stock Entry")""",
}


def get_tool_category(tool_name: str) -> str:
    """取得工具所屬類別"""
    for category, tools in DEPRECATED_TOOLS.items():
        if tool_name in tools:
            return category
    return "其他"


def get_all_deprecated_tools() -> list[str]:
    """取得所有要停用的工具名稱"""
    tools = []
    for category_tools in DEPRECATED_TOOLS.values():
        tools.extend(category_tools)
    return tools


def disable_tool_in_content(content: str, tool_name: str) -> tuple[str, bool]:
    """
    在工具函數中加入停用程式碼

    Returns:
        (modified_content, was_modified)
    """
    category = get_tool_category(tool_name)
    guidance = ERPNEXT_GUIDANCE.get(category, "請使用 ERPNext MCP 工具操作")

    deprecation_return = f'''    # [DEPRECATED] 此工具已停用，功能已遷移至 ERPNext
    return """❌ 此功能已遷移至 ERPNext

{guidance}

或直接在 ERPNext 系統操作：http://ct.erp"""

    # 以下為原始程式碼，保留供參考
'''

    # 找到函數定義和 docstring
    # 匹配 @mcp.tool() + async def xxx(...) -> str: + """docstring"""
    pattern = rf'(async def {tool_name}\([^)]*\)[^:]*:\s*\n\s*"""[^"]*""")\n(\s+)'

    match = re.search(pattern, content)
    if not match:
        return content, False

    # 檢查是否已經停用
    after_pos = match.end()
    next_content = content[after_pos:after_pos + 100]
    if "[DEPRECATED]" in next_content:
        return content, False

    # 在 docstring 後插入停用程式碼
    insert_pos = match.end()
    indent = match.group(2)  # 保持縮排
    new_content = content[:match.start(2)] + deprecation_return + content[match.end(1)+1:]

    return new_content, True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="停用 CTOS MCP 工具")
    parser.add_argument("--dry-run", action="store_true", help="只顯示將修改的工具，不實際修改")
    parser.add_argument("--category", type=str, help="只處理特定類別（專案管理、廠商管理、物料管理）")
    parser.add_argument("--tool", type=str, help="只處理特定工具")
    args = parser.parse_args()

    print("=" * 50)
    print("停用 CTOS MCP 工具")
    print("=" * 50)

    if not MCP_SERVER_PATH.exists():
        print(f"錯誤：找不到 {MCP_SERVER_PATH}")
        return

    content = MCP_SERVER_PATH.read_text()
    original_content = content

    # 決定要處理的工具
    tools_to_process = []
    if args.tool:
        tools_to_process = [args.tool]
    elif args.category:
        tools_to_process = DEPRECATED_TOOLS.get(args.category, [])
        if not tools_to_process:
            print(f"錯誤：找不到類別 '{args.category}'")
            print(f"可用類別：{list(DEPRECATED_TOOLS.keys())}")
            return
    else:
        tools_to_process = get_all_deprecated_tools()

    print(f"\n將處理 {len(tools_to_process)} 個工具")

    if args.dry_run:
        for category, tools in DEPRECATED_TOOLS.items():
            category_tools = [t for t in tools if t in tools_to_process]
            if category_tools:
                print(f"\n{category}:")
                for t in category_tools:
                    print(f"  - {t}")
        print("\n[DRY-RUN] 不實際修改檔案")
        return

    print("\n開始處理...")
    modified_count = 0
    skipped_count = 0

    for tool_name in tools_to_process:
        content, was_modified = disable_tool_in_content(content, tool_name)
        if was_modified:
            print(f"  + 停用: {tool_name}")
            modified_count += 1
        else:
            # 檢查是否已停用
            if f"async def {tool_name}" in content and "[DEPRECATED]" in content:
                print(f"  ✓ 已停用: {tool_name}")
            else:
                print(f"  ⚠ 找不到: {tool_name}")
            skipped_count += 1

    if content != original_content:
        MCP_SERVER_PATH.write_text(content)
        print(f"\n✓ 已更新 {MCP_SERVER_PATH}")
        print(f"  停用: {modified_count} 個工具")
        print(f"  跳過: {skipped_count} 個工具")
    else:
        print("\n沒有需要更新的工具")


if __name__ == "__main__":
    main()
