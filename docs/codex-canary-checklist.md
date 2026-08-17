# Codex Canary 查詢與人工檢查清單

Codex ACP failover 的 canary 觀察工具與驗收規則。搭配 `openspec/changes/add-codex-acp-failover` 的 8.x（分階段 caller 整合）與 9.7（canary 連續觀察）使用。

## 驗收底線

- **每一筆 canary 請求都必須能辨識 provider**：`ai_logs.parsed_response->routing->provider`、service log 的 `ai_route` 行、或兩者。**無法辨識 provider 的請求視為驗收失敗**（9.7 不可追查請求）。
- 任何重複副作用（同一請求觸發兩次工具副作用）視為驗收失敗。
- 任何安全退化（工具白名單外的呼叫、身份注入異常、terminal/file-write 事件）視為驗收失敗。

## Provider 辨識查詢

### ai_logs（parsed_response.routing 由 `attach_routing_metadata()` 寫入）

> 注意（2026-08-17 實測修正）：`create_log` 存入時會先 `json.dumps`，jsonb 欄位裡是「JSON 字串」，
> 要先 `#>> '{}'` 取出再 cast 回 jsonb；且舊資料含 NUL 跳脫序列（反斜線 u0000） 會讓 cast 直接報錯，
> 必須用 `WITH ... MATERIALIZED` 先以 text 條件過濾，再做 jsonb 萃取。

```bash
# 最近 20 筆含 routing 資訊的請求：provider、route reason、實際模型
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "
WITH logs AS MATERIALIZED (
  SELECT id, context_type, model, success, duration_ms, created_at,
         (parsed_response #>> '{}')::jsonb AS pr
  FROM ai_logs
  WHERE parsed_response IS NOT NULL
    AND parsed_response::text NOT LIKE '%\\\\u0000%'
)
SELECT id, context_type, model,
       pr #>> '{routing,provider}'     AS provider,
       pr #>> '{routing,route_reason}' AS route_reason,
       pr #>> '{routing,actual_model}' AS actual_model,
       success, duration_ms, created_at
FROM logs WHERE pr ? 'routing'
ORDER BY created_at DESC LIMIT 20"

# 驗收失敗偵測：canary context 中「無法辨識 provider」的請求（應為 0 筆）
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "
WITH logs AS MATERIALIZED (
  SELECT id, context_type, created_at,
         CASE WHEN parsed_response IS NULL
                OR parsed_response::text LIKE '%\\\\u0000%'
              THEN NULL
              ELSE (parsed_response #>> '{}')::jsonb END AS pr
  FROM ai_logs
  WHERE context_type IN ('internal_admin', 'internal_test', 'test')  -- 依 canary allowlist 調整
    AND created_at > now() - interval '72 hours'
)
SELECT id, context_type, created_at
FROM logs WHERE pr IS NULL OR NOT pr ? 'routing'
ORDER BY created_at DESC"

# provider 分佈與成功率（觀察期彙總）
docker exec ching-tech-os-db psql -U ching_tech -d ching_tech_os -c "
WITH logs AS MATERIALIZED (
  SELECT success, duration_ms, created_at,
         (parsed_response #>> '{}')::jsonb AS pr
  FROM ai_logs
  WHERE parsed_response IS NOT NULL
    AND parsed_response::text NOT LIKE '%\\\\u0000%'
    AND created_at > now() - interval '72 hours'
)
SELECT pr #>> '{routing,provider}' AS provider,
       count(*) AS total,
       count(*) FILTER (WHERE success) AS ok,
       round(avg(duration_ms)) AS avg_ms
FROM logs WHERE pr ? 'routing'
GROUP BY 1 ORDER BY 2 DESC"
```

> `model` 欄位維持記錄 requested role（sonnet/opus/haiku），既有 AI 管理統計不受影響；實際 provider/模型只看 `routing`。

### Service log（structured log）

```bash
# 路由決策：provider、route reason、latency、tool 數
journalctl -u ching-tech-os --since "1 hour ago" --no-pager | grep 'ai_route'

# Codex 執行：queue 等待與 circuit 狀態
journalctl -u ching-tech-os --since "1 hour ago" --no-pager | grep 'codex_call\|codex_queue_timeout'

# Codex 工具事件（只有名稱與耗時，無輸入參數）
journalctl -u ching-tech-os --since "1 hour ago" --no-pager | grep 'codex_tool_'

# 錯誤分類（auth_error / binary_missing / mcp_startup_error / overload / protocol_error）
journalctl -u ching-tech-os --since "24 hours ago" --no-pager | grep 'category='
```

### 即時狀態（admin API）

```bash
# provider readiness、circuit 狀態與 Claude usage 快照（需 admin session）
curl -s -H "Cookie: session=<admin-session>" \
  http://localhost:8088/api/ai/providers/status | jq
```

## 人工檢查清單（每日 / 觀察期結束時）

- [ ] canary 請求總數與 provider 分佈符合預期（auto mode 未啟用時應全為 forced 路徑）
- [ ] 「無法辨識 provider」查詢結果為 **0 筆**
- [ ] Codex 請求無重複副作用：抽查 `parsed_response->tool_calls`，同一請求無重複的寫入型工具
- [ ] 無安全事件：log 中無 `security_violation`、`permission_denied`、`terminal_denied`、`file_write_denied`
- [ ] `codex_queue_timeout` 次數在可接受範圍；circuit 未長期 open
- [ ] 錯誤分類無異常暴增（特別是 `auth_error` → 登入過期，需以 service user 重新 `codex login`）
- [ ] log 中無 credentials / token / MCP headers（抽查 `grep -iE 'bearer|sk-|token=' `，命中即立刻處理）
- [ ] usage snapshot 的 state 大部分時間為 fresh；長期 stale/error 需查 usage monitor

## 異常處置（kill switch）

1. `.env` 設 `AI_PROVIDER_MODE=claude`（forced Claude）。
2. 清空 `AI_PROVIDER_CANARY_CONTEXTS` / `AI_PROVIDER_CANARY_AGENTS`。
3. `sudo systemctl restart ching-tech-os`。
4. 保留 routing/error log 供事後分析，不清理 journal。
