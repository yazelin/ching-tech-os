## MODIFIED Requirements

### Requirement: 生成簡報 MCP 工具
The system SHALL provide a `generate_presentation` MCP tool that generates PowerPoint presentations.

The tool SHALL accept the following parameters:
- `topic`: Presentation topic (required if no outline_json)
- `num_slides`: Number of slides (2-20, default 5)
- `style`: Predefined style name (professional, casual, creative, minimal, dark, tech, nature, warm, elegant)
- `include_images`: Whether to auto-add images (default true)
- `image_source`: Image source (pexels, huggingface, nanobanana)
- `outline_json`: Direct outline JSON to skip AI generation
- `design_json`: Complete design specification from presentation designer (NEW)

When `design_json` is provided:
- The system SHALL use the design specification for colors, typography, layout, and decorations
- The system SHALL ignore the `style` parameter
- The system SHALL extract slides from `design_json.slides` if present

The `design_json` structure SHALL include:
- `design.colors`: Color scheme (background, title, subtitle, text, bullet, accent)
- `design.typography`: Font settings (title_font, title_size, body_font, body_size)
- `design.layout`: Layout settings (title_align, content_columns, image_position)
- `design.decorations`: Decoration settings (title_underline, accent_bar, page_number)
- `slides`: Array of slide definitions

#### Scenario: Generate with design_json
- **WHEN** user calls `generate_presentation` with `design_json` parameter
- **THEN** the system uses the design specification for visual styling
- **AND** the system generates a PowerPoint file with custom colors, fonts, and decorations

#### Scenario: Generate with predefined style (backward compatible)
- **WHEN** user calls `generate_presentation` with `style` parameter only
- **THEN** the system uses the predefined style configuration
- **AND** the behavior remains unchanged from Phase 1

#### Scenario: Invalid design_json format
- **WHEN** user provides malformed `design_json`
- **THEN** the system returns an error message describing the issue
- **AND** the system does not generate a partial presentation
