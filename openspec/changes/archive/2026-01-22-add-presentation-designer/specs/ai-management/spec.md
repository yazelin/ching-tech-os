## ADDED Requirements

### Requirement: Presentation Designer Agent
The system SHALL provide a presentation designer AI agent that generates visual design specifications for presentations.

The agent SHALL be registered in the `ai_agents` table with:
- `code`: "presentation_designer"
- `name`: "簡報設計師"
- `model`: "sonnet" (for design quality)
- `prompt_name`: "presentation_designer"

The agent SHALL consider the following factors when designing:
- Content type (technical, marketing, financial, product)
- Target audience (client, internal team, investor, technical staff)
- Presentation scenario (projection, online meeting, print, tablet)
- Brand/industry tone (tech, manufacturing, eco-friendly, luxury)
- Slide count and information density

The agent SHALL output a complete `design_json` specification including:
- Color scheme appropriate for the scenario
- Typography settings for readability
- Layout configuration for content organization
- Decoration elements for visual interest

#### Scenario: Design for client presentation
- **WHEN** the agent receives content for a client presentation
- **THEN** the agent outputs a professional design with polished colors
- **AND** the design emphasizes credibility and visual appeal

#### Scenario: Design for internal sharing
- **WHEN** the agent receives content for internal team sharing
- **THEN** the agent outputs a casual design with friendly colors
- **AND** the design prioritizes clarity over formality

#### Scenario: Design for projection display
- **WHEN** the presentation scenario is large venue projection
- **THEN** the agent outputs a dark background design
- **AND** the agent increases font sizes for visibility
- **AND** the agent uses high contrast colors

### Requirement: Presentation Designer Prompt
The system SHALL store a `presentation_designer` prompt in the `prompts` table.

The prompt SHALL instruct the AI to:
- Analyze the provided content and context
- Apply professional design principles (color theory, visual hierarchy, contrast)
- Output valid JSON matching the `design_json` schema
- Provide appropriate fallback values for optional fields

The prompt SHALL be updatable via database without code changes.

#### Scenario: Prompt retrieval
- **WHEN** the presentation designer agent is invoked
- **THEN** the system retrieves the prompt from the `prompts` table
- **AND** the system uses the latest prompt content

#### Scenario: Prompt update
- **WHEN** an administrator updates the prompt in the database
- **THEN** subsequent agent invocations use the updated prompt
- **AND** no service restart is required
