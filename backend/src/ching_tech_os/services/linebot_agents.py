"""Line Bot Agent 初始化與管理

在應用程式啟動時確保預設的 Line Bot Agent 存在。
"""

import logging

from . import ai_manager
from ..models.ai import AiPromptCreate, AiAgentCreate

logger = logging.getLogger("linebot_agents")

# Agent 名稱常數
AGENT_LINEBOT_PERSONAL = "linebot-personal"
AGENT_LINEBOT_GROUP = "linebot-group"

# 完整的 linebot-personal prompt
LINEBOT_PERSONAL_PROMPT = """你是擎添工業的 AI 助理，透過 Line 與用戶進行個人對話。

你可以使用以下工具：

【專案查詢】
- query_project: 查詢專案（可用關鍵字搜尋，取得專案 ID）
- get_project_milestones: 取得專案里程碑（需要 project_id）
- get_project_meetings: 取得專案會議記錄（需要 project_id）
- get_project_members: 取得專案成員與聯絡人（需要 project_id）

【知識庫】
- search_knowledge: 搜尋知識庫（輸入關鍵字，回傳標題列表）
- get_knowledge_item: 取得知識庫文件完整內容（輸入 kb_id，如 kb-001）
- update_knowledge_item: 更新知識庫文件（可更新標題、內容、分類、標籤）
- delete_knowledge_item: 刪除知識庫文件
- add_note: 新增筆記到知識庫（輸入標題和內容）

使用工具的流程：
1. 先用 query_project 搜尋專案名稱取得 ID
2. 查詢知識庫時，先用 search_knowledge 找到文件 ID，再用 get_knowledge_item 取得完整內容
3. 用戶要求「記住」或「記錄」某事時，使用 add_note 新增筆記
4. 用戶要求修改或更新知識時，使用 update_knowledge_item
5. 用戶要求刪除知識時，使用 delete_knowledge_item

對話管理：
- 用戶可以發送 /新對話 或 /reset 來清除對話歷史，開始新對話
- 當用戶說「忘記之前的對話」或類似內容時，建議他們使用 /新對話 指令

回應原則：
- 使用繁體中文
- 語氣親切專業
- 善用工具查詢資訊，主動提供有用的資料
- 回覆用戶時不要顯示 UUID，只顯示名稱"""

# 精簡的 linebot-group prompt
LINEBOT_GROUP_PROMPT = """你是擎添工業的 AI 助理，在 Line 群組中協助回答問題。

可用工具：
- query_project / get_project_milestones / get_project_meetings / get_project_members: 專案相關查詢
- search_knowledge / get_knowledge_item: 知識庫查詢
- add_note: 新增筆記
- summarize_chat: 取得群組聊天記錄摘要

回應原則：
- 使用繁體中文
- 回覆簡潔（不超過 200 字）
- 善用工具查詢資訊
- 不顯示 UUID，只顯示名稱"""

# 預設 Agent 設定
DEFAULT_LINEBOT_AGENTS = [
    {
        "name": AGENT_LINEBOT_PERSONAL,
        "display_name": "Line 個人助理",
        "description": "Line Bot 個人對話 Agent",
        "model": "claude-sonnet",
        "prompt": {
            "name": AGENT_LINEBOT_PERSONAL,
            "display_name": "Line 個人助理 Prompt",
            "category": "linebot",
            "content": LINEBOT_PERSONAL_PROMPT,
            "description": "Line Bot 個人對話使用，包含完整 MCP 工具說明",
        },
    },
    {
        "name": AGENT_LINEBOT_GROUP,
        "display_name": "Line 群組助理",
        "description": "Line Bot 群組對話 Agent",
        "model": "claude-haiku",
        "prompt": {
            "name": AGENT_LINEBOT_GROUP,
            "display_name": "Line 群組助理 Prompt",
            "category": "linebot",
            "content": LINEBOT_GROUP_PROMPT,
            "description": "Line Bot 群組對話使用，精簡版包含 MCP 工具說明",
        },
    },
]


async def ensure_default_linebot_agents() -> None:
    """
    確保預設的 Line Bot Agent 存在。

    如果 Agent 已存在則跳過（保留使用者修改）。
    如果不存在則建立 Agent 和對應的 Prompt。
    """
    for agent_config in DEFAULT_LINEBOT_AGENTS:
        agent_name = agent_config["name"]

        # 檢查 Agent 是否存在
        existing_agent = await ai_manager.get_agent_by_name(agent_name)
        if existing_agent:
            logger.debug(f"Agent '{agent_name}' 已存在，跳過建立")
            continue

        # 檢查 Prompt 是否存在
        prompt_config = agent_config["prompt"]
        existing_prompt = await ai_manager.get_prompt_by_name(prompt_config["name"])

        if existing_prompt:
            prompt_id = existing_prompt["id"]
            logger.debug(f"Prompt '{prompt_config['name']}' 已存在，使用現有 Prompt")
        else:
            # 建立 Prompt
            prompt_data = AiPromptCreate(
                name=prompt_config["name"],
                display_name=prompt_config["display_name"],
                category=prompt_config["category"],
                content=prompt_config["content"],
                description=prompt_config["description"],
            )
            new_prompt = await ai_manager.create_prompt(prompt_data)
            prompt_id = new_prompt["id"]
            logger.info(f"已建立 Prompt: {prompt_config['name']}")

        # 建立 Agent
        agent_data = AiAgentCreate(
            name=agent_config["name"],
            display_name=agent_config["display_name"],
            description=agent_config["description"],
            model=agent_config["model"],
            system_prompt_id=prompt_id,
            is_active=True,
        )
        await ai_manager.create_agent(agent_data)
        logger.info(f"已建立 Agent: {agent_name}")


async def get_linebot_agent(is_group: bool) -> dict | None:
    """
    取得 Line Bot Agent 設定。

    Args:
        is_group: 是否為群組對話

    Returns:
        Agent 設定字典，包含 model 和 system_prompt
        如果找不到則回傳 None
    """
    agent_name = AGENT_LINEBOT_GROUP if is_group else AGENT_LINEBOT_PERSONAL
    return await ai_manager.get_agent_by_name(agent_name)
