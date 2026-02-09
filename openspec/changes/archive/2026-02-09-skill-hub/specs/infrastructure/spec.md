## ADDED Requirements

### Requirement: ClawHub CLI 部署

install.sh SHALL 包含 ClawHub CLI 的安裝步驟。

#### Scenario: 全新安裝
- **WHEN** 執行 install.sh
- **THEN** 安裝 Node.js（如未安裝）
- **AND** 執行 `npm install -g clawhub`
- **AND** 驗證 `clawhub --version` 可執行

#### Scenario: ClawHub 未安裝時的降級
- **GIVEN** clawhub CLI 未安裝
- **WHEN** 管理員嘗試搜尋或安裝 ClawHub skill
- **THEN** API 回傳 503 錯誤
- **AND** 錯誤訊息提示需要安裝 clawhub
- **AND** 其他 Skills 功能（列表、編輯、移除）正常運作
