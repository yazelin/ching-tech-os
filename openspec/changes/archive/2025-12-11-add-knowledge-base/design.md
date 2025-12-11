## Context

ChingTech OS 需要一個企業級知識庫系統，能夠：
- 管理**多個專案**的知識（RosAGV、ChingTech-OS、其他專案...）
- 支援**各層級使用者**（工程師、PM、管理層）
- 提供**通用知識**（公司規範、技術標準、SOP）
- 支援**完整追蹤**（作者、來源、關聯、版本歷史）
- **全文搜尋**與**標籤過濾**

### 參考架構

RosAGV `docs-ai/` 提供了單一專案的三層架構參考：
- Context（背景知識）
- Knowledge（領域專業）
- Operations（操作指導）

但我們需要擴展為**跨專案企業知識庫**。

## Goals / Non-Goals

### Goals
- 設計一個能夠容納多專案、多類型知識的組織架構
- 支援靈活的標籤系統（專案、類型、層級、主題）
- 完整追蹤知識來源與關聯
- 檔案式儲存（Git 友善）
- 高效本機搜尋（ripgrep）

### Non-Goals（第一階段）
- 不實作權限控制（暫時全公開）
- 不實作 AI Agents 整合（另開提案）
- 不實作 PostgreSQL 索引（視檔案量後續評估）

## Decisions

### 決策 1: 知識組織架構

#### 方案 A: 專案為主 (Project-First)

```
data/knowledge/
├── _common/                    # 通用知識（跨專案）
│   ├── company/               # 公司規範
│   ├── standards/             # 技術標準
│   └── templates/             # 範本文件
├── rosagv/                     # RosAGV 專案
│   ├── context/
│   ├── knowledge/
│   └── operations/
├── ching-tech-os/              # ChingTech-OS 專案
│   └── ...
└── project-x/                  # 其他專案
    └── ...
```

**優點：**
- 專案邊界清晰
- 可直接整合專案 Git（submodule 或 symlink）
- 專案成員容易找到相關知識
- 與 RosAGV docs-ai 架構相容

**缺點：**
- 跨專案知識難以定位（例：通用 PostgreSQL 知識放哪？）
- 相同主題分散在不同專案
- 搜尋時需要知道屬於哪個專案

---

#### 方案 B: 知識類型為主 (Type-First)

```
data/knowledge/
├── technical/                  # 技術知識
│   ├── languages/             # 程式語言
│   ├── databases/             # 資料庫
│   ├── protocols/             # 協定規範
│   └── frameworks/            # 框架工具
├── business/                   # 業務知識
│   ├── processes/             # 業務流程
│   ├── clients/               # 客戶相關
│   └── products/              # 產品知識
├── operations/                 # 操作知識
│   ├── sop/                   # 標準作業程序
│   ├── troubleshooting/       # 故障排除
│   └── deployment/            # 部署維運
├── reference/                  # 參考資料
│   ├── architecture/          # 架構設計
│   ├── standards/             # 標準規範
│   └── glossary/              # 術語詞彙
└── projects/                   # 專案特定（以標籤區分）
    └── ...
```

**優點：**
- 知識按主題聚合
- 學習特定技術時路徑清晰
- 通用知識有明確位置

**缺點：**
- 專案邊界模糊
- 分類標準可能因人而異
- 難以與專案 Git 整合

---

#### 方案 C: 混合式 + 標籤系統 (Hybrid + Tags) ⭐ 推薦

```
data/knowledge/
├── entries/                    # 所有知識條目（扁平化，Git 追蹤）
│   ├── kb-001-postgresql-jsonb-best-practices.md
│   ├── kb-002-rosagv-vehicle-types.md
│   ├── kb-003-python-uv-package-manager.md
│   └── ...
├── assets/                     # 小型附件（Git 追蹤）
│   └── images/                # 小圖片（< 1MB）
└── index.json                  # 知識索引（由系統維護）

# NAS 上的大型附件（不進 Git）
//192.168.11.50/擎添開發/ching-tech-os/knowledge/
├── attachments/               # 大型附件（影片、大圖、文件）
│   ├── kb-001/               # 依知識 ID 分資料夾
│   │   ├── demo-video.mp4
│   │   └── large-diagram.png
│   └── kb-002/
│       └── architecture.pdf
└── exports/                   # 匯出備份
```

每個知識檔案使用 **YAML Front Matter** 定義完整元資料：

```yaml
---
id: kb-002
title: AGV 車型特性和應用場景
type: knowledge          # context | knowledge | operations | reference
category: technical      # technical | business | operations | reference
subcategory: agv-domain

# 標籤系統（多維度過濾）
tags:
  projects: [rosagv]                    # 適用專案
  roles: [engineer, pm]                 # 適用角色
  topics: [agv, vehicle, hardware]      # 主題標籤
  level: intermediate                    # beginner | intermediate | advanced

# 來源追蹤
source:
  project: rosagv
  path: docs-ai/knowledge/agv-domain/vehicle-types.md
  commit: abc1234

# 關聯
related:
  - kb-015  # 關聯知識 ID
  - kb-023
references:
  - https://kuka.com/fleet-api
  - rosagv:app/agv_base/README.md

# 元資料
author: ct
created_at: 2024-11-25
updated_at: 2024-12-01
version: 2
---

# AGV 車型特性和應用場景

（知識內容...）
```

**優點：**
- 扁平化儲存 + 標籤系統 = 最大靈活性
- 多維度搜尋（專案、角色、主題、層級）
- Git 友善（每個檔案獨立追蹤）
- 易於遷移（只是 Markdown + 元資料）
- AI Agents 可直接讀取 Front Matter 決定相關性

**缺點：**
- 需要維護索引（index.json）
- 元資料欄位需要標準化
- 初期分類需要定義標籤體系

---

### 最終選擇: 方案 C（混合式 + 標籤系統）

理由：
1. 扁平化結構避免分類爭議
2. 標籤系統提供多維度過濾能力
3. 完整追蹤需求可在 Front Matter 滿足
4. 未來 AI Agents 可解析 Front Matter 提供智慧推薦

---

### 決策 2: 搜尋實作

#### 全文搜尋: ripgrep (rg)

本機執行 `rg` 進行 Markdown 內容搜尋：
- 速度極快（數十萬檔案毫秒級）
- 支援正則表達式
- 支援檔案類型過濾

#### 標籤過濾: 記憶體索引

載入 `index.json` 到記憶體：
- 按標籤過濾候選檔案
- 再用 rg 搜尋內容
- 或直接返回標籤匹配結果

#### 未來擴展: PostgreSQL FTS

當檔案量超過 1000+ 時，考慮：
- 將元資料同步到 PostgreSQL
- 使用 pg_trgm 或 FTS 索引
- 保持檔案為 source of truth

---

### 決策 3: 知識 ID 與命名規則

#### ID 格式: `kb-{序號}`
- `kb-001`
- `kb-002`
- `kb-003`

序號由系統自動分配（遞增）。

#### 檔名格式: `kb-{序號}-{slug}.md`
- `kb-001-postgresql-jsonb.md`
- `kb-002-rosagv-vehicle-types.md`
- `kb-003-python-uv-guide.md`

**slug 產生規則**（支援人類與 AI Agents 建立）：
- 由建立者（人類或 AI Agent）提供
- 建議格式：kebab-case，2-5 個單字
- 系統不強制驗證 slug 格式，僅確保唯一性
- 若 slug 重複，自動附加 `-2`, `-3` 等後綴

**AI Agents 建立知識時**：
- Agent 呼叫 API 時提供 `title` 和建議的 `slug`
- 系統自動分配 `id`（下一個序號）
- Agent 可在 `author` 欄位標註自己（如 `ai:knowledge-agent`）

---

### 決策 4: 標籤體系（初版）

#### projects（專案）
- `rosagv`
- `ching-tech-os`
- `common`（通用）

#### type（知識類型）
- `context` - 背景知識
- `knowledge` - 專業知識
- `operations` - 操作指導
- `reference` - 參考資料

#### category（分類）
- `technical` - 技術類
- `business` - 業務類
- `management` - 管理類

#### roles（適用角色）
- `engineer` - 工程師
- `pm` - 專案經理
- `manager` - 管理層
- `all` - 所有人

#### level（難度層級）
- `beginner` - 入門
- `intermediate` - 中階
- `advanced` - 進階

#### topics（自由標籤）
- 由作者自行定義
- 例: `python`, `agv`, `postgresql`, `api`, `deployment`

## Risks / Trade-offs

### Risk 1: 標籤不一致
**問題**: 不同作者對標籤理解不同
**緩解**:
- 提供標籤下拉選單（預定義選項）
- 定期標籤清理/合併

### Risk 2: 索引同步
**問題**: index.json 與檔案不同步
**緩解**:
- 每次 CRUD 操作更新索引
- 提供「重建索引」功能
- Git hooks 驗證同步

### Risk 3: 檔案數量增長
**問題**: 數千檔案後搜尋變慢
**緩解**:
- rg 本身效能優秀
- 必要時遷移到 PostgreSQL 索引

---

### 決策 5: 附件儲存策略

#### 小型附件（< 1MB）
- 儲存於 `data/knowledge/assets/images/`
- 隨專案 Git 追蹤
- 知識內以相對路徑引用：`../assets/images/xxx.png`

#### 大型附件（≥ 1MB）
- 儲存於 NAS：`//192.168.11.50/擎添開發/ching-tech-os/knowledge/attachments/{kb-id}/`
- 不進入 Git（避免 repo 膨脹）
- 知識內以特殊協定引用：`nas://knowledge/attachments/kb-001/video.mp4`
- 前端顯示時透過後端 API 代理存取

#### 附件元資料
在知識 Front Matter 中記錄附件清單：

```yaml
attachments:
  - type: image
    path: ../assets/images/diagram.png
    size: 50KB
  - type: video
    path: nas://knowledge/attachments/kb-001/demo.mp4
    size: 25MB
    description: 操作示範影片
```

---

### 決策 6: Git 版本歷史

#### UI 功能
- 在知識檢視頁面提供「版本歷史」按鈕
- 顯示該知識檔案的 Git commit 歷史
- 每筆記錄顯示：時間、作者、commit message
- 可展開查看該版本的內容差異（diff）

#### 後端 API
- `GET /api/knowledge/{id}/history` - 取得版本歷史
- `GET /api/knowledge/{id}/version/{commit}` - 取得特定版本內容
- `GET /api/knowledge/{id}/diff/{commit1}/{commit2}` - 取得兩版本差異

#### 技術實作
- 使用 `git log --follow` 追蹤檔案歷史（含重命名）
- 使用 `git show {commit}:{path}` 取得特定版本
- 使用 `git diff` 產生差異

#### AI Agents 整合（未來）
- AI Agent 可查詢知識的歷史演變
- 回答「這個知識以前是怎樣的？現在變成怎樣？」
- 追蹤知識的修改脈絡

---

## Migration Plan

### 第一階段: 基礎建設
- 建立 `data/knowledge/` 目錄結構
- 建立 NAS 知識庫共享資料夾
- 實作 CRUD API
- 實作基本 UI

### 第二階段: 版本歷史
- 實作 Git 版本歷史 API
- 實作版本歷史 UI

### 第三階段: AI Agents 整合
- 另開提案處理
- 提供知識查詢 API 給其他 Agents

---

### 決策 7: CSS 設計系統整合

#### 全域 CSS 變數

知識庫 UI 使用 `main.css` 定義的全域 CSS 變數，確保設計一致性：

**表面與邊框變數：**
```css
--bg-surface: rgba(0, 0, 0, 0.1);
--bg-surface-dark: rgba(0, 0, 0, 0.2);
--bg-surface-darker: rgba(0, 0, 0, 0.3);
--bg-overlay: rgba(0, 0, 0, 0.6);
--bg-overlay-dark: rgba(0, 0, 0, 0.85);
--border-subtle: rgba(255, 255, 255, 0.05);
--border-light: rgba(255, 255, 255, 0.1);
--border-medium: rgba(255, 255, 255, 0.15);
--border-strong: rgba(255, 255, 255, 0.2);
--hover-bg: rgba(255, 255, 255, 0.1);
```

**強調色變數：**
```css
--accent-bg-subtle: rgba(33, 212, 253, 0.1);
--accent-bg-light: rgba(33, 212, 253, 0.15);
--accent-bg-medium: rgba(33, 212, 253, 0.2);
--accent-border: rgba(33, 212, 253, 0.3);
```

#### 應用規則
- 所有元件應使用全域變數而非硬編碼 rgba 值
- Modal 背景使用 `--bg-overlay-dark` 確保可讀性
- 懸停狀態使用 `--hover-bg` 或 `--accent-bg-subtle`
- 按鈕使用全域 `.btn` 類別而非自訂樣式

---

### 決策 8: 附件區固定底部佈局

#### 佈局結構

使用 Flexbox 實現內容區可捲動、附件區固定底部：

```
#kbContentView (flex: column, height: 100%)
├── .kb-content-header (flex-shrink: 0)
├── .kb-content-tags (flex-shrink: 0)
├── .kb-content-body (flex: 1, overflow-y: auto)
└── .kb-attachments (flex-shrink: 0, max-height: 180px)
```

#### 優點
- 使用者無需捲動即可看到附件
- 內容過長時僅內容區捲動
- 附件區有最大高度限制，超出時內部捲動

---

### 決策 9: 刪除知識連帶刪除附件

#### 行為定義
- 刪除知識時自動刪除所有關聯附件
- 本機附件（`data/knowledge/assets/`）直接刪除
- NAS 附件（`//192.168.11.50/.../attachments/{kb-id}/`）透過 SMB 刪除
- 刪除 NAS 上的知識目錄（若存在）

#### 設計考量
- 目前每個附件僅屬於單一知識，無跨知識共享
- 若未來需要附件共享，需引入參考計數機制
- 刪除失敗時記錄錯誤但不阻擋知識刪除

## Open Questions (已解決)

1. ~~**知識命名 slug 規則**~~ → 由建立者（人類或 AI）決定，系統僅確保唯一性
2. ~~**附件管理**~~ → 小檔案 Git 追蹤，大檔案存 NAS
3. ~~**版本控制**~~ → UI 顯示 Git 版本歷史，支援差異比較
4. ~~**匯入工具**~~ → 不需要，手動或 AI Agent 逐筆建立
5. ~~**附件共享**~~ → 目前設計每個附件僅屬於單一知識
