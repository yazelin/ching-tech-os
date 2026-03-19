# 月度 Token 用量上限 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按用戶限制受限模式的月度 token 用量，防止單一用戶消耗整月預算。

**Architecture:** 複用 bot_usage_tracking 表，新增 `period_type='monthly_tokens'` 計數器。AI 呼叫前檢查額度，呼叫後累加實際 token 數。設定放在 Agent settings 中。

**Tech Stack:** Python asyncpg, PostgreSQL bot_usage_tracking 表

---

## File Structure

| 操作 | 檔案 | 職責 |
|------|------|------|
| 修改 | `backend/src/ching_tech_os/services/bot/rate_limiter.py` | 新增 token 額度檢查 + 累加函式 |
| 修改 | `backend/src/ching_tech_os/services/bot/identity_router.py` | 插入檢查 + 呼叫後累加 |
| 新增 | `backend/tests/test_token_limit.py` | 單元測試 |

---

### Task 1: rate_limiter 新增 token 額度函式

**Files:**
- Modify: `backend/src/ching_tech_os/services/bot/rate_limiter.py`
- Test: `backend/tests/test_token_limit.py`

- [ ] **Step 1: 建立測試檔，寫 check_monthly_tokens 的 failing tests**

```python
"""月度 Token 用量上限測試"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _make_conn_mock(token_count: int = 0):
    """建立模擬 DB 連線"""
    row = {"message_count": token_count}
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(return_value=None),
        __aexit__=AsyncMock(return_value=None),
    ))
    return conn


class TestCheckMonthlyTokens:
    """月度 token 額度檢查"""

    @pytest.mark.asyncio
    async def test_no_limit_configured(self):
        """沒有設定上限 → allow"""
        from ching_tech_os.services.bot.rate_limiter import check_monthly_tokens
        allowed, msg = await check_monthly_tokens("user-1", monthly_limit=0)
        assert allowed is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_under_limit(self):
        """未超額 → allow"""
        from ching_tech_os.services.bot.rate_limiter import check_monthly_tokens
        conn = _make_conn_mock(token_count=1000)
        ctx = MagicMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=None))
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens("user-1", monthly_limit=500000)
            assert allowed is True

    @pytest.mark.asyncio
    async def test_over_limit(self):
        """超額 → reject"""
        from ching_tech_os.services.bot.rate_limiter import check_monthly_tokens
        conn = _make_conn_mock(token_count=600000)
        ctx = MagicMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=None))
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens("user-1", monthly_limit=500000)
            assert allowed is False
            assert msg is not None

    @pytest.mark.asyncio
    async def test_custom_message(self):
        """自訂超額訊息"""
        from ching_tech_os.services.bot.rate_limiter import check_monthly_tokens
        conn = _make_conn_mock(token_count=600000)
        ctx = MagicMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=None))
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens(
                "user-1", monthly_limit=500000,
                custom_message="本月額度已用完，limit={limit}",
            )
            assert "500000" in msg

    @pytest.mark.asyncio
    async def test_db_error_failopen(self):
        """DB 錯誤 → fail-open"""
        from ching_tech_os.services.bot.rate_limiter import check_monthly_tokens
        ctx = MagicMock(
            __aenter__=AsyncMock(side_effect=RuntimeError("db down")),
            __aexit__=AsyncMock(return_value=None),
        )
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            allowed, msg = await check_monthly_tokens("user-1", monthly_limit=500000)
            assert allowed is True


class TestRecordTokenUsage:
    """token 用量記錄"""

    @pytest.mark.asyncio
    async def test_record_tokens(self):
        """記錄 token 用量（UPSERT monthly_tokens）"""
        from ching_tech_os.services.bot.rate_limiter import record_token_usage
        conn = _make_conn_mock()
        ctx = MagicMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=None))
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            await record_token_usage("user-1", input_tokens=1000, output_tokens=200)
            conn.execute.assert_called_once()
            # 確認 SQL 包含 monthly_tokens 和正確的 token 數
            sql = conn.execute.call_args[0][0]
            assert "monthly_tokens" in sql

    @pytest.mark.asyncio
    async def test_record_zero_tokens(self):
        """token 為 0 或 None → 不記錄"""
        from ching_tech_os.services.bot.rate_limiter import record_token_usage
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection") as mock_gc:
            await record_token_usage("user-1", input_tokens=0, output_tokens=0)
            mock_gc.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_db_error_silent(self):
        """DB 錯誤 → 靜默失敗，不阻擋"""
        from ching_tech_os.services.bot.rate_limiter import record_token_usage
        ctx = MagicMock(
            __aenter__=AsyncMock(side_effect=RuntimeError("db down")),
            __aexit__=AsyncMock(return_value=None),
        )
        with patch("ching_tech_os.services.bot.rate_limiter.get_connection", return_value=ctx):
            # 不應拋出例外
            await record_token_usage("user-1", input_tokens=1000, output_tokens=200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_token_limit.py -v`
Expected: ImportError — `check_monthly_tokens` / `record_token_usage` 不存在

- [ ] **Step 3: 實作 check_monthly_tokens 和 record_token_usage**

在 `rate_limiter.py` 新增：

```python
def _current_monthly_key() -> str:
    """取得當月的 period_key（如 '2026-03'）"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


async def check_monthly_tokens(
    bot_user_id: str,
    monthly_limit: int,
    custom_message: str | None = None,
) -> tuple[bool, str | None]:
    """檢查月度 token 額度

    Args:
        bot_user_id: bot_users.id (UUID 字串)
        monthly_limit: 月度 token 上限（0 表示不限制）
        custom_message: 自訂超額訊息（支援 {limit}、{count} 變數）

    Returns:
        (是否允許, 拒絕訊息) - 允許時拒絕訊息為 None
    """
    if not monthly_limit or monthly_limit <= 0:
        return True, None

    monthly_key = _current_monthly_key()

    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT message_count FROM bot_usage_tracking
                WHERE bot_user_id = $1
                  AND period_type = 'monthly_tokens'
                  AND period_key = $2
                """,
                bot_user_id,
                monthly_key,
            )
            current_tokens = row["message_count"] if row else 0

            if current_tokens >= monthly_limit:
                if custom_message:
                    msg = custom_message.format_map(
                        _SafeFormatMap(limit=str(monthly_limit), count=str(current_tokens))
                    )
                else:
                    msg = (
                        f"您本月的使用額度已達上限（{monthly_limit:,} tokens）。\n"
                        "請下個月再試，或綁定帳號以獲得完整服務。"
                    )
                return False, msg

            return True, None

    except Exception:
        logger.exception("月度 token 額度檢查失敗，允許通過（fail-open）")
        return True, None


async def record_token_usage(
    bot_user_id: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> None:
    """記錄 token 用量（UPSERT 月度計數器）

    Args:
        bot_user_id: bot_users.id (UUID 字串)
        input_tokens: 輸入 token 數
        output_tokens: 輸出 token 數
    """
    total = (input_tokens or 0) + (output_tokens or 0)
    if total <= 0:
        return

    monthly_key = _current_monthly_key()

    try:
        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO bot_usage_tracking (bot_user_id, period_type, period_key, message_count)
                VALUES ($1, 'monthly_tokens', $2, $3)
                ON CONFLICT (bot_user_id, period_type, period_key)
                DO UPDATE SET message_count = bot_usage_tracking.message_count + $3,
                             updated_at = NOW()
                """,
                bot_user_id,
                monthly_key,
                total,
            )
    except Exception:
        logger.exception("記錄 token 用量失敗")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_token_limit.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/ching_tech_os/services/bot/rate_limiter.py backend/tests/test_token_limit.py
git commit -m "feat: 新增月度 token 用量檢查與記錄函式"
```

---

### Task 2: identity_router 整合 token 限制

**Files:**
- Modify: `backend/src/ching_tech_os/services/bot/identity_router.py`
- Test: `backend/tests/test_token_limit.py`（追加整合測試）

- [ ] **Step 1: 寫整合測試**

在 `test_token_limit.py` 追加：

```python
class TestIdentityRouterIntegration:
    """identity_router 整合測試"""

    @pytest.mark.asyncio
    async def test_token_limit_exceeded_skips_ai(self):
        """月度 token 超額 → 直接回覆，不呼叫 AI"""
        # mock agent 帶 monthly_token_limit 設定
        # mock check_monthly_tokens 回傳 (False, "超額訊息")
        # 確認 call_claude 未被呼叫
        ...

    @pytest.mark.asyncio
    async def test_tokens_recorded_after_ai_call(self):
        """AI 呼叫後記錄 token 用量"""
        # mock call_claude 回傳含 token 統計的 response
        # 確認 record_token_usage 被呼叫且參數正確
        ...
```

- [ ] **Step 2: 在 identity_router.py 插入 token 檢查（rate_limiter 之後、Intent Guard 之前）**

```python
    # 月度 token 額度檢查
    if bot_user_id:
        from .rate_limiter import check_monthly_tokens

        monthly_limit = agent_settings.get("monthly_token_limit", 0)
        if monthly_limit:
            monthly_msg = agent_settings.get("monthly_token_limit_msg")
            allowed, deny_msg = await check_monthly_tokens(
                bot_user_id,
                monthly_limit=monthly_limit,
                custom_message=monthly_msg,
            )
            if not allowed:
                return deny_msg
```

- [ ] **Step 3: 在 AI 呼叫後累加 token**

在 `response = await call_claude(...)` 之後、記錄 AI Log 之前：

```python
    # 記錄 token 用量（月度計數器）
    if bot_user_id and response.input_tokens:
        from .rate_limiter import record_token_usage
        await record_token_usage(
            bot_user_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
```

- [ ] **Step 4: Run all tests**

Run: `cd backend && uv run pytest tests/test_token_limit.py tests/test_identity_router.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `cd backend && uv run pytest -x -q`
Expected: ALL PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add backend/src/ching_tech_os/services/bot/identity_router.py backend/tests/test_token_limit.py
git commit -m "feat: 整合月度 token 限制到受限模式流程"
```

---

### Task 3: 端對端驗證 + 文件更新

- [ ] **Step 1: 在 jfmskin-edu Agent settings 加入 token 限制設定**

```sql
UPDATE ai_agents
SET settings = settings || '{"monthly_token_limit": 500000, "monthly_token_limit_msg": "本月使用額度已達上限，請下個月再試。"}'::jsonb
WHERE name = 'jfmskin-edu';
```

- [ ] **Step 2: 重啟服務，從 Line Bot 測試**

- [ ] **Step 3: 更新文件**

更新 `docs/ai-agent-design.md`、`docs/ai-management.md`、`docs/module-index.md` 補充 token 限制說明。

- [ ] **Step 4: Commit all**

```bash
git add docs/
git commit -m "docs: 補充月度 token 限制說明"
```

---

### Task 4: Close GitHub Issue

- [ ] **Close #134**，加上完成說明
