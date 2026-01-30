# file-storage spec delta

## ADDED Requirements

### Requirement: shared zone 多掛載點路徑解析
path_manager SHALL 支援 `shared://` 協議下的多個子來源對應到不同掛載點。

#### Scenario: 解析帶來源前綴的 shared 路徑
- **GIVEN** path_manager 設定了 projects 和 circuits 子來源
- **WHEN** 解析 `shared://circuits/線路圖A/xxx.dwg`
- **THEN** 對應到本機路徑 `/mnt/nas/circuits/線路圖A/xxx.dwg`

#### Scenario: 解析 projects 子來源路徑
- **GIVEN** path_manager 設定了 projects 子來源
- **WHEN** 解析 `shared://projects/亦達光學/layout.pdf`
- **THEN** 對應到本機路徑 `/mnt/nas/projects/亦達光學/layout.pdf`

#### Scenario: 向後相容舊格式
- **GIVEN** 資料庫中存在舊格式 `shared://亦達光學/layout.pdf`（無子來源前綴）
- **WHEN** 解析該路徑
- **THEN** 第一段 `亦達光學` 不是已知子來源名稱
- **AND** fallback 對應到 `/mnt/nas/projects/亦達光學/layout.pdf`
