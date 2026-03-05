## 1. extends Agent seed 函式

- [x] 1.1 在 `linebot_agents.py` 新增 `_seed_extends_agents()` 函式：掃描 `extends/*/clients/*/agents/*.md`，解析 frontmatter + body，轉換為 agent_config dict
- [x] 1.2 在 `ensure_default_linebot_agents()` 尾端呼叫 `_seed_extends_agents()`

## 2. 驗證

- [x] 2.1 重啟 CTOS 或手動呼叫，確認 `jfmskin-full` Agent 出現在 `ai_agents` 表
- [x] 2.2 確認 `jfmskin-edu` Agent 未被覆蓋（已存在跳過）
- [x] 2.3 確認 prompt 內容與 `extends/his/clients/jfmskin/agents/jfmskin-full.md` 一致
