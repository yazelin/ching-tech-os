## MODIFIED Requirements

### Requirement: 生成簡報 MCP 工具
The system SHALL provide a `generate_presentation` MCP tool that generates HTML or PDF presentations using Marp.

The tool SHALL accept the following parameters:
- `topic`: Presentation topic (required if no outline_json)
- `num_slides`: Number of slides (2-20, default 5)
- `theme`: Marp built-in theme (default, gaia, gaia-invert, uncover)
- `include_images`: Whether to auto-add images (default true)
- `image_source`: Image source (pexels, huggingface, nanobanana)
- `outline_json`: Direct outline JSON to skip AI generation
- `output_format`: Output format (html, pdf; default html)

The `theme` parameter SHALL support:
- `uncover`: Dark projection (dark gray background) - default
- `gaia`: Professional blue (dark blue gradient background)
- `gaia-invert`: Light blue (white background)
- `default`: Minimal white (white background, black text)

#### Scenario: Generate HTML presentation
- **WHEN** user calls `generate_presentation` with `output_format="html"`
- **THEN** the system generates an HTML file using Marp
- **AND** the HTML file can be viewed directly in a browser

#### Scenario: Generate PDF presentation
- **WHEN** user calls `generate_presentation` with `output_format="pdf"`
- **THEN** the system generates a PDF file using Marp
- **AND** the PDF file can be downloaded and printed

#### Scenario: Generate with theme
- **WHEN** user calls `generate_presentation` with `theme="gaia"`
- **THEN** the system uses the Marp gaia theme (dark blue gradient)

#### Scenario: Invalid theme
- **WHEN** user provides an invalid theme value
- **THEN** the system returns an error message listing valid themes

### Requirement: 簡報主題選項
`generate_presentation` 工具 SHALL 支援以下 Marp 內建主題：
- `gaia`（預設）：專業藍，深藍漸層背景，適合正式提案
- `gaia-invert`：亮色藍，白色背景，適合列印
- `default`：簡約白，白底黑字，適合技術文件
- `uncover`：深色投影，深灰背景，適合晚間活動

#### Scenario: 使用專業藍主題
- **WHEN** 呼叫 `generate_presentation(topic="季度報告", theme="gaia")`
- **THEN** 簡報使用深藍漸層背景、白色文字

#### Scenario: 使用亮色主題
- **WHEN** 呼叫 `generate_presentation(topic="技術文件", theme="gaia-invert")`
- **THEN** 簡報使用白色背景、深色文字，適合列印閱讀

### Requirement: 簡報檔案命名與儲存
系統 SHALL 將生成的簡報儲存至 NAS，並使用結構化的檔名。

#### Scenario: HTML 檔案命名格式
- **WHEN** 生成主題為「AI 應用」的 HTML 簡報
- **THEN** 檔名格式為 `AI應用_20260122_143052.html`（主題_日期_時間）
- **AND** 儲存路徑為 `/mnt/nas/projects/ai-presentations/`

#### Scenario: PDF 檔案命名格式
- **WHEN** 生成主題為「AI 應用」的 PDF 簡報
- **THEN** 檔名格式為 `AI應用_20260122_143052.pdf`（主題_日期_時間）
- **AND** 儲存路徑為 `/mnt/nas/projects/ai-presentations/`

#### Scenario: 檔名包含特殊字元
- **GIVEN** 主題包含特殊字元如「產品/服務介紹」
- **WHEN** 生成簡報
- **THEN** 系統清理檔名中的特殊字元（斜線、冒號等）
- **AND** 產出有效的檔案名稱

## REMOVED Requirements

### Requirement: 簡報風格選項
**Reason**: 已被「簡報主題選項」取代，使用 Marp 內建主題而非自訂風格
**Migration**: 將 `style` 參數改為 `theme` 參數，對應關係如下：
- `professional` → `gaia`
- `casual` → `gaia-invert`
- `creative` → `gaia`
- `minimal` → `default`
- `dark` → `uncover`
- `tech` → `gaia`
