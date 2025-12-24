## ADDED Requirements

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
