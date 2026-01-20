# Design: 多租戶 Line Bot 架構

## Context

目前系統使用環境變數存放單一 Line Bot 的憑證：
- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`

多租戶模式下，每個租戶需要能使用自己的 Line Bot，讓：
1. 各公司的 Bot 有自己的名稱和頭像
2. 群組自動歸屬到對應租戶
3. 平台管理員不需要手動管理群組

## Goals / Non-Goals

### Goals
- 每個租戶可設定自己的 Line Bot 憑證（獨立 Bot 模式）
- 支援多租戶共用預設 Bot（共用 Bot 模式）
- Webhook 自動識別請求來自哪個租戶的 Bot
- 群組自動或安全地歸屬對應租戶
- 租戶管理員可自行管理 Bot 設定
- **確保不同租戶的資料完全隔離，不可能混雜**

### Non-Goals
- 不支援一個租戶使用多個 Bot（一對一關係）
- 不自動建立 Line Bot（租戶需在 Line Developer Console 手動建立）
- 不處理 Line Bot 的 LIFF 或 Rich Menu（未來擴充）
- 不支援「第一個說話的人決定租戶」（有安全風險）

## Security Analysis: 資料隔離

### 威脅模型

**攻擊者**：租戶 B 的惡意用戶
**目標**：將租戶 A 的群組綁定到租戶 B，竊取資料

**攻擊情境**：
1. 攻擊者（租戶 B 用戶）被邀請到租戶 A 的 Line 群組
2. 共用 Bot 已在群組中
3. 攻擊者嘗試將群組綁定到租戶 B

### 各模式安全性分析

#### 獨立 Bot 模式（完全安全 ✓）
```
租戶 A 的 Bot → Webhook 簽名驗證 → 只會產生租戶 A 的群組
租戶 B 的 Bot → Webhook 簽名驗證 → 只會產生租戶 B 的群組
```
- 攻擊者無法將租戶 A 的群組綁定到租戶 B
- 因為租戶 A 的群組用的是租戶 A 的 Bot

#### 共用 Bot + 自動綁定（不安全 ✗，不採用）
```
共用 Bot 加入群組 → 第一個說話的人決定租戶
```
- 攻擊者只要先說話，就能把群組綁到自己的租戶
- **絕對不採用此方案**

#### 共用 Bot + 指令綁定（安全 ✓）
```
共用 Bot 加入群組 → 群組未綁定，Bot 不回應
用戶發送 /綁定 ABC公司 → 驗證：
  1. 發送者是否已綁定 CTOS 帳號？
  2. 發送者是否屬於「ABC公司」租戶？
  3. 兩者都通過 → 綁定成功
```
- 攻擊者無法綁定到自己的租戶（除非他也屬於那個租戶）
- 攻擊者無法綁定到受害者的租戶（不知道公司代碼或驗證失敗）

### 安全決策

1. **獨立 Bot 模式**：完全信任簽名驗證，自動歸屬
2. **共用 Bot 模式**：必須使用指令綁定，驗證發送者身份
3. **禁止自動綁定**：絕不根據「第一個說話的人」決定租戶

## Decisions

### Decision 1: 憑證儲存位置

**選項 A：存在 TenantSettings JSON 中**
```python
class TenantSettings(BaseModel):
    line_channel_id: str | None = None
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None
```

**選項 B：獨立 tenants 欄位**
```sql
ALTER TABLE tenants ADD COLUMN line_channel_id VARCHAR(100);
ALTER TABLE tenants ADD COLUMN line_channel_secret VARCHAR(200);
ALTER TABLE tenants ADD COLUMN line_channel_access_token VARCHAR(500);
```

**決定：選項 A（TenantSettings JSON）**
- 理由：
  - 與現有 settings 架構一致
  - 不需要修改 tenants 表結構
  - 未來擴充更多設定更容易

### Decision 2: 憑證加密

**選項 A：明文儲存**
- 簡單，但安全性較低

**選項 B：應用層加密（AES-256）**
- 使用環境變數的 key 加密
- 讀取時解密

**選項 C：資料庫層加密（pgcrypto）**
- 使用 PostgreSQL 內建加密

**決定：選項 B（應用層 AES-256 加密）**
- 理由：
  - 平衡安全性與實作複雜度
  - 加密 key 在環境變數，資料庫洩漏時憑證安全
  - 不依賴特定資料庫功能

### Decision 3: Webhook 租戶識別

**選項 A：URL 路徑區分**
```
/api/linebot/webhook/{tenant_code}
```
- 每個租戶不同的 webhook URL

**選項 B：遍歷簽名驗證**
```python
for tenant in tenants:
    if verify_signature(body, tenant.secret):
        return tenant
```
- 單一 webhook URL，驗證時識別

**選項 C：Channel ID 查詢**
- Line webhook 不帶 channel_id，無法使用

**決定：選項 B（遍歷簽名驗證）**
- 理由：
  - 所有 Bot 使用同一個 webhook URL，設定簡單
  - 租戶數量通常不多（<100），效能可接受
  - 如效能成為問題，可加入快取優化

### Decision 4: 預設 Bot 處理

**選項 A：必須設定租戶 Bot**
- 沒設定的租戶無法使用 Line Bot

**選項 B：Fallback 到環境變數 Bot**
- 未設定的租戶使用預設 Bot
- 群組歸屬到 default 租戶

**決定：選項 B（Fallback 機制）**
- 理由：
  - 向後相容現有部署
  - 小租戶不需要建立自己的 Bot
  - default 租戶作為「共用 Bot」使用

### Decision 5: 共用 Bot 群組綁定機制

**選項 A：第一個說話的人決定租戶**
- 全自動
- **安全風險：可被惡意綁定**

**選項 B：指令綁定 + 身份驗證**
- 需要發送 `/綁定 公司代碼`
- 驗證發送者屬於該租戶

**選項 C：群組管理員確認**
- Bot 詢問確認，需要 Line 群組管理員回應
- 實作複雜，需要追蹤確認狀態

**決定：選項 B（指令綁定 + 身份驗證）**
- 理由：
  - 安全：驗證發送者身份，防止跨租戶綁定
  - 簡單：一次指令即可完成
  - 明確：用戶知道群組屬於哪個租戶

## Architecture

### 整體架構

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  租戶 A 的 Bot  │     │  租戶 B 的 Bot  │     │   共用 Bot      │
│  (公司A助理)    │     │  (公司B助理)    │     │  (擎添助理)     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │  Webhook Endpoint       │
                   │  /api/linebot/webhook   │
                   └────────────┬────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │  簽名驗證 & 租戶識別    │
                   │  1. 遍歷租戶 secrets    │
                   │  2. 驗證 X-Line-Sig     │
                   │  3. 識別對應租戶        │
                   └────────────┬────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
  ┌──────▼──────┐       ┌───────▼───────┐      ┌───────▼───────┐
  │ 獨立 Bot    │       │ 共用 Bot      │      │ 共用 Bot      │
  │ 自動歸屬    │       │ 群組已綁定    │      │ 群組未綁定    │
  │ tenant_id   │       │ 使用綁定的    │      │ 等待 /綁定    │
  │ = 該租戶    │       │ tenant_id     │      │ 指令          │
  └─────────────┘       └───────────────┘      └───────────────┘
```

### 共用 Bot 群組綁定流程

```
┌──────────────────────────────────────────────────────────────────┐
│                    共用 Bot 群組綁定流程                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Bot 加入群組                                                 │
│     └─→ 建立 line_groups，tenant_id = NULL                      │
│                                                                  │
│  2. 任何訊息（非綁定指令）                                        │
│     └─→ Bot 回覆：「請先使用 /綁定 公司代碼 綁定此群組」          │
│                                                                  │
│  3. 用戶發送：/綁定 ABC公司                                      │
│     └─→ 驗證流程：                                               │
│         ├─ 發送者是否已綁定 CTOS？ ──✗──→ 「請先綁定帳號」       │
│         ├─ 公司代碼是否存在？     ──✗──→ 「公司代碼無效」        │
│         └─ 發送者是否屬於該租戶？ ──✗──→ 「您不屬於此公司」      │
│                                    ──✓──→ 綁定成功！             │
│                                                                  │
│  4. 綁定成功                                                     │
│     └─→ 更新 line_groups.tenant_id = ABC公司的 tenant_id        │
│     └─→ Bot 回覆：「此群組已綁定到 ABC公司」                     │
│                                                                  │
│  5. 後續訊息正常處理                                             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 新群組加入 Bot
1. 使用者將租戶 A 的 Bot 加入群組
2. Line 發送 JoinEvent 到 webhook
3. 系統遍歷租戶 secrets 驗證簽名
4. 找到租戶 A 的 secret 驗證成功
5. 建立 `line_groups` 記錄，`tenant_id = 租戶 A`
6. 使用租戶 A 的 `access_token` 回覆歡迎訊息

### 群組訊息處理
1. 群組內使用者發送訊息 @ Bot
2. Line 發送 MessageEvent 到 webhook
3. 系統驗證簽名識別租戶
4. 使用該租戶的 AI 設定處理訊息
5. 使用該租戶的 `access_token` 回覆

## Risks / Trade-offs

### Risk 1: 簽名驗證效能
- **風險**：租戶數量增加時，遍歷驗證可能變慢
- **緩解**：
  - 快取 tenant secrets（TTL 5 分鐘）
  - 優先驗證最近活躍的租戶
  - 未來可考慮建立 channel_id → tenant_id 快取

### Risk 2: 憑證外洩
- **風險**：資料庫洩漏導致憑證外洩
- **緩解**：應用層加密，需要同時取得資料庫和加密 key

### Risk 3: 租戶設定錯誤
- **風險**：租戶填錯憑證導致 webhook 驗證失敗
- **緩解**：
  - 提供「測試連線」功能驗證憑證
  - 錯誤時 fallback 到預設 Bot

## Migration Plan

### Phase 1: 新增欄位
1. 建立 migration 新增 TenantSettings 欄位
2. 現有租戶的 Line Bot 設定為 null
3. 所有請求繼續使用環境變數 Bot

### Phase 2: 實作多租戶驗證
1. 修改 webhook 驗證邏輯
2. 有設定的租戶使用自己的 Bot
3. 未設定的租戶 fallback 到預設 Bot

### Phase 3: UI 設定
1. 租戶管理介面新增 Line Bot 設定
2. 租戶管理員可自行設定

### Rollback
- 刪除租戶的 Line Bot 設定即可回復到使用預設 Bot
- 不需要修改群組資料

## Open Questions

1. **是否需要「測試 webhook」功能**？讓租戶驗證設定是否正確
2. **舊群組遷移**：現有群組（tenant_id = default）是否需要遷移？
3. **共用 Bot 情境**：是否支援多個租戶共用同一個 Bot？（設定相同的 channel_id）
