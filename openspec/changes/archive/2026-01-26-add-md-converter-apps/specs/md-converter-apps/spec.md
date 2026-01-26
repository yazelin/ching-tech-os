# md-converter-apps Specification

## Purpose
提供 Markdown 轉換工具的桌面應用程式整合，讓使用者可以在 CTOS 桌面環境中使用 MD2PPT 和 MD2Doc 外部服務。

## ADDED Requirements

### Requirement: External App Framework
系統 SHALL 提供通用的外部應用程式框架，用於以 iframe 方式整合外部 Web 服務。

#### Scenario: 建立外部應用程式視窗
- **GIVEN** 使用者點擊外部應用程式圖示
- **WHEN** 系統呼叫 `ExternalAppModule.open(config)`
- **THEN** 系統建立包含 iframe 的視窗
- **AND** iframe src 設為配置的 URL

#### Scenario: 顯示載入狀態
- **GIVEN** 外部應用程式視窗已開啟
- **WHEN** iframe 尚未載入完成
- **THEN** 視窗顯示載入中的動畫和文字

#### Scenario: 載入完成
- **GIVEN** 外部應用程式視窗正在載入
- **WHEN** iframe 觸發 load 事件
- **THEN** 隱藏載入狀態
- **AND** 顯示 iframe 內容

#### Scenario: 防止重複開啟
- **GIVEN** 外部應用程式視窗已開啟
- **WHEN** 使用者再次點擊同一應用程式圖示
- **THEN** 系統聚焦到已開啟的視窗
- **AND** 不建立新視窗

---

### Requirement: MD2PPT Application
系統 SHALL 提供 MD2PPT 應用程式，讓使用者可以將 Markdown 轉換為 PowerPoint 簡報。

#### Scenario: 桌面圖示顯示
- **GIVEN** 使用者登入並進入桌面
- **WHEN** 桌面渲染應用程式圖示
- **THEN** 顯示 MD2PPT 應用程式圖示
- **AND** 圖示名稱為「MD2PPT」
- **AND** 使用 PowerPoint 相關圖示

#### Scenario: 開啟 MD2PPT 視窗
- **GIVEN** 使用者在桌面
- **WHEN** 點擊 MD2PPT 應用程式圖示
- **THEN** 系統開啟 MD2PPT 視窗
- **AND** 視窗標題為「MD2PPT」
- **AND** 視窗預設尺寸為 1000x700

#### Scenario: 載入 MD2PPT 服務
- **GIVEN** MD2PPT 視窗已開啟
- **WHEN** iframe 載入完成
- **THEN** 顯示 https://md-2-ppt-evolution.vercel.app/ 的內容

---

### Requirement: MD2Doc Application
系統 SHALL 提供 MD2Doc 應用程式，讓使用者可以將 Markdown 轉換為 Word 文件。

#### Scenario: 桌面圖示顯示
- **GIVEN** 使用者登入並進入桌面
- **WHEN** 桌面渲染應用程式圖示
- **THEN** 顯示 MD2Doc 應用程式圖示
- **AND** 圖示名稱為「MD2Doc」
- **AND** 使用 Word 相關圖示

#### Scenario: 開啟 MD2Doc 視窗
- **GIVEN** 使用者在桌面
- **WHEN** 點擊 MD2Doc 應用程式圖示
- **THEN** 系統開啟 MD2Doc 視窗
- **AND** 視窗標題為「MD2Doc」
- **AND** 視窗預設尺寸為 1000x700

#### Scenario: 載入 MD2Doc 服務
- **GIVEN** MD2Doc 視窗已開啟
- **WHEN** iframe 載入完成
- **THEN** 顯示 https://md-2-doc-evolution.vercel.app/ 的內容

---

### Requirement: Cross-Origin Fallback
系統 SHALL 在 iframe 無法載入時提供替代方案。

#### Scenario: iframe 禁止嵌入
- **GIVEN** 外部服務設定 X-Frame-Options 禁止嵌入
- **WHEN** 使用者開啟應用程式視窗
- **THEN** 視窗顯示錯誤訊息
- **AND** 提供「在新視窗開啟」按鈕

---

## Related Specs
- `code-editor` - 參考 iframe 整合模式
- `web-desktop` - 桌面應用程式管理
