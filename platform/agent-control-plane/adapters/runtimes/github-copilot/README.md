# GitHub Copilot Runtime Adapter

This scaffold owns GitHub Copilot capability declarations, supported-version
ranges, mapping tests, and renderers when concrete runtime translation is
required.

List any checked-in generated installation files, one repository-relative path
per line, in `generated-projections.txt`.

Canonical behavior remains under `../../../agent-assets/`. Repository-native
installation files remain under `.github/copilot-instructions.md` and the
agent-related `.github/` paths and should contain only discovery links,
canonical imports, generated projections, or explicitly approved GitHub
Copilot configuration.

Other `.github/` content, such as Actions and Dependabot configuration, is
ordinary GitHub repository configuration and is outside this adapter boundary.
