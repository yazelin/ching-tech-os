# Spec: 權限模型改善

## Purpose
實作 deny-by-default 權限模型，讓外部安裝的 skill 預設僅管理員可用，防止未經審核的 skill 暴露給所有使用者。

### Requirement: 信任等級
系統 SHALL 為每個 skill 標記信任等級：

| 等級 | 判定條件 | 預設 requires_app |
|------|----------|------------------|
| `builtin` | 無 `_meta.json` | 維持現有設定 |
| `private` | `_meta.json.owner` 與系統設定的 admin handle 一致 | admin 設定 |
| `community` | 其他 ClawHub 安裝的 skill | `"admin"`（全關） |

#### Scenario: 安裝外部 skill
WHEN 管理員從 ClawHub 安裝一個 community skill
THEN `requires_app` 預設為 `"admin"`
AND 前端顯示引導：「此 Skill 目前僅管理員可用，要開放嗎？」
AND 提供快捷選項：「所有人」/「管理員」/「自訂」

#### Scenario: 安裝自己發布的 skill
WHEN 管理員安裝的 skill 的 owner handle 與系統管理員一致
THEN 信任等級標記為 `private`
AND 仍然預設 `requires_app: "admin"`，但可以自動建議更寬鬆的權限

### Requirement: 特殊權限值
系統 SHALL 支援以下特殊 `requires_app` 值：
- 空字串 `""` — 所有登入使用者可用（向後相容）
- `"admin"` — 僅管理員
- 其他值 — 需要對應的 app 權限

### Requirement: Skill 狀態燈號
前端 Skill 列表 SHALL 顯示狀態燈號：

| 燈號 | CSS class | 條件 |
|------|-----------|------|
| 🟢 綠色 | `.skill-status-ok` | ENV 齊全 + 權限已設 |
| 🟡 黃色 | `.skill-status-warning` | 缺必填 ENV 或權限為預設 admin |
| 🔴 紅色 | `.skill-status-error` | 載入失敗 |

#### Scenario: 狀態計算
WHEN 系統載入 skill 列表
THEN 對每個 skill 計算狀態：
- 檢查 `metadata.openclaw.requires.env` 中 required=true 的 key 是否都有設定
- 檢查 `requires_app` 是否仍為安裝預設值（未經管理員確認）
AND 狀態欄位包含在 API 回應中

### Requirement: 內建 skill 權限補齊
現有 7 個內建 skill SHALL 補上正確的 `requires_app`：
- `base` → `""`（所有人）
- `ai-assistant` → `""`（所有人）
- `file-manager` → `"file_manager"`
- `inventory` → `"inventory"`
- `knowledge` → `"knowledge_base"`
- `printer` → `"printer"`（Phase 4 遷移後）
- `project` → `"project"`
