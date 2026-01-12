## ADDED Requirements

### Requirement: Line Bot 知識庫來源自動判斷

Line Bot 在建立知識時 SHALL 根據對話來源自動設定知識的 scope 和關聯。

#### Scenario: 個人聊天建立個人知識

- **WHEN** 使用者透過 Line Bot 個人聊天建立知識
- **AND** 使用者已綁定 CTOS 帳號
- **THEN** 知識的 scope 設為 personal
- **AND** 知識的 owner 設為該使用者帳號
- **AND** 該使用者可以編輯和刪除此知識

#### Scenario: 綁定專案的群組建立專案知識

- **WHEN** 使用者透過 Line Bot 群組聊天建立知識
- **AND** 群組已綁定專案
- **THEN** 知識的 scope 設為 project
- **AND** 知識的 project_id 設為群組綁定的專案 ID
- **AND** 專案成員可以編輯和刪除此知識

#### Scenario: 未綁定專案的群組建立全域知識

- **WHEN** 使用者透過 Line Bot 群組聊天建立知識
- **AND** 群組未綁定專案
- **THEN** 知識的 scope 設為 global
- **AND** 需要全域權限才能編輯

#### Scenario: 未綁定帳號的使用者

- **WHEN** 使用者透過 Line Bot 建立知識
- **AND** 使用者未綁定 CTOS 帳號
- **THEN** 知識的 scope 設為 global
- **AND** 知識的 author 設為 linebot
