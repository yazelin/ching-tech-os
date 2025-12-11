# code-editor Specification

## Purpose
TBD - created by archiving change add-code-editor. Update Purpose after archive.
## Requirements
### Requirement: Code Editor Window
系統 SHALL 提供程式編輯器視窗，使用 code-server 提供完整的 VS Code 體驗。

#### Scenario: 開啟程式編輯器
- **WHEN** 使用者點擊 Taskbar 上的程式編輯器圖示
- **THEN** 系統開啟程式編輯器視窗
- **AND** 視窗內嵌入 code-server 介面

#### Scenario: 編輯器視窗尺寸
- **WHEN** 程式編輯器視窗開啟
- **THEN** 視窗以較大的預設尺寸顯示（1200x800）
- **AND** 使用者可以調整視窗大小或最大化

#### Scenario: 編輯器載入狀態
- **WHEN** code-server 尚未載入完成
- **THEN** 視窗顯示載入中的提示

#### Scenario: 編輯器連線失敗
- **WHEN** code-server 服務未啟動或無法連線
- **THEN** 視窗顯示錯誤訊息
- **AND** 提示使用者檢查服務狀態

---

### Requirement: Code Server Service
系統 SHALL 透過 Docker 運行 code-server 服務。

#### Scenario: 服務啟動
- **WHEN** 執行 start.sh dev 命令
- **THEN** code-server 容器隨 docker compose 啟動
- **AND** 服務在 port 8443 提供存取

#### Scenario: 工作目錄掛載
- **WHEN** code-server 啟動
- **THEN** 專案根目錄掛載為工作目錄
- **AND** 使用者可以在編輯器中瀏覽和編輯專案檔案

#### Scenario: Git 整合
- **WHEN** 使用者在 code-server 中執行 Git 操作
- **THEN** 使用主機的 SSH key 和 gitconfig
- **AND** commit 顯示正確的作者資訊

#### Scenario: 設定持久化
- **WHEN** 使用者安裝擴充功能或修改設定
- **THEN** 設定保存在 Docker volume 中
- **AND** 重啟後設定保留

