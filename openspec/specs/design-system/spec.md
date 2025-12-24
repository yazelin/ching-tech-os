# design-system Specification

## Purpose
TBD - created by archiving change unify-ui-design-system. Update Purpose after archive.
## Requirements
### Requirement: CSS Design Token System

系統 SHALL 在 `main.css` 中定義完整的 CSS 變數（Design Tokens），涵蓋所有 UI 顏色。

#### Scenario: 標籤顏色變數定義
- **WHEN** 開發者需要使用標籤顏色
- **THEN** 可使用 `--tag-color-*` 系列變數
- **AND** 包含 purple、green、yellow、pink、blue、gray 六種語義化顏色

#### Scenario: 模態框變數定義
- **WHEN** 開發者需要建立模態框
- **THEN** 可使用 `--modal-bg` 和 `--modal-border` 變數
- **AND** 確保模態框背景為不透明色彩

#### Scenario: 終端機主題變數定義
- **WHEN** 開發者需要設定終端機樣式
- **THEN** 可使用 `--terminal-*` 系列變數
- **AND** 包含背景色、前景色及 ANSI 16 色

### Requirement: No Hardcoded Colors Outside Root

所有 CSS 檔案中的顏色值 SHALL 透過 CSS 變數引用，不得在 `:root` 定義區以外直接使用 HEX 或 rgb/rgba 硬編碼顏色。

#### Scenario: 檢查硬編碼顏色
- **WHEN** 開發者審查 CSS 檔案
- **THEN** 除了 `main.css :root` 區塊外，不應發現 `#XXXXXX` 或 `rgb()`/`rgba()` 形式的顏色值
- **AND** 所有顏色都透過 `var(--*)` 引用

#### Scenario: rgba 透明度運算
- **WHEN** 需要帶透明度的品牌色
- **THEN** 使用 `rgba(var(--accent-rgb), 0.x)` 形式
- **OR** 使用已定義的 `--*-bg-subtle` 系列變數

### Requirement: Theme Switching Support

CSS 變數架構 SHALL 支援主題切換功能。

#### Scenario: 切換至亮色主題
- **WHEN** 系統設定 `data-theme="light"` 於 html 元素
- **THEN** 所有使用 CSS 變數的 UI 元件應自動套用亮色主題顏色
- **AND** 不需要修改任何元件的 CSS 檔案

### Requirement: Brand Color Consistency

所有 UI 顏色 SHALL 符合 `design/brand.md` 定義的品牌色票。

#### Scenario: 主色系使用
- **WHEN** UI 需要使用主要品牌色
- **THEN** 必須使用 ChingTech Blue `#1C4FA8`、Deep Industrial Navy `#0F1C2E`、AI Neon Cyan `#21D4FD`
- **AND** 透過 `--color-primary`、`--color-background`、`--color-accent` 變數引用

#### Scenario: 狀態色使用
- **WHEN** UI 需要表示成功、警告、錯誤狀態
- **THEN** 必須使用 Action Green `#4CC577`、Warning Amber `#FFC557`、Error Red `#E65050`
- **AND** 透過 `--color-success`、`--color-warning`、`--color-error` 變數引用

### Requirement: CSS Variable Naming Convention
The system SHALL use industry-standard CSS variable naming conventions for text colors.

#### Scenario: Text color variables use --text-* prefix
- **WHEN** defining text color CSS variables
- **THEN** the variables SHALL be named with `--text-` prefix (e.g., `--text-primary`, `--text-secondary`, `--text-muted`)
- **AND** the `--color-` prefix SHALL be reserved for semantic colors (brand, status)

#### Scenario: Background variables use --bg-* prefix
- **WHEN** defining background color CSS variables
- **THEN** the variables SHALL be named with `--bg-` prefix (e.g., `--bg-surface`, `--bg-overlay`)

#### Scenario: Semantic colors use --color-* prefix
- **WHEN** defining brand or status colors
- **THEN** the variables SHALL use `--color-` prefix (e.g., `--color-primary`, `--color-success`, `--color-error`)

### Requirement: Theme Storage
The system SHALL store user theme preferences exclusively in browser localStorage.

#### Scenario: Theme persistence via localStorage
- **WHEN** user changes the theme
- **THEN** the preference SHALL be saved to localStorage with key `ching-tech-os-theme`
- **AND** the preference SHALL NOT be sent to the backend API

#### Scenario: Theme loaded on page load
- **WHEN** any page loads (including login page)
- **THEN** the system SHALL read theme from localStorage
- **AND** apply the theme immediately to prevent flash of wrong colors

### Requirement: Login Page Theme Toggle
The login page SHALL provide a theme toggle button for users to switch between dark and light modes before logging in.

#### Scenario: Theme toggle on login page
- **WHEN** user is on the login page
- **THEN** a theme toggle button SHALL be visible
- **AND** clicking the toggle SHALL switch between dark and light themes
- **AND** the selection SHALL persist via localStorage

