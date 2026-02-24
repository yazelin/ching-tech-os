## ADDED Requirements

### Requirement: ENABLED_MODULES 環境變數
`config.py` SHALL 提供 `enabled_modules` 設定欄位，由 `ENABLED_MODULES` 環境變數驅動。

#### Scenario: 預設值
- **WHEN** `ENABLED_MODULES` 環境變數未設定
- **THEN** `settings.enabled_modules` SHALL 為 `"*"`（代表啟用全部模組）

#### Scenario: 自訂模組清單
- **WHEN** `ENABLED_MODULES` 設為 `"core,knowledge-base,line-bot"`
- **THEN** `settings.enabled_modules` SHALL 為該字串值

### Requirement: main.py 條件路由註冊
`main.py` SHALL 使用 `importlib` 動態載入啟用模組的 router，取代頂層靜態 import。

#### Scenario: 移除頂層靜態 import
- **WHEN** 系統啟動
- **THEN** `main.py` SHALL 不再有 `from .api import linebot_router, telegram_router, ...` 的頂層 import
- **THEN** 路由註冊 SHALL 改為遍歷 `get_module_registry()` 動態載入

#### Scenario: lifespan 條件初始化
- **WHEN** 模組定義了 `lifespan_startup`
- **THEN** 只有啟用的模組的 startup 函式 SHALL 被呼叫
- **THEN** 停用模組的 startup SHALL 跳過
