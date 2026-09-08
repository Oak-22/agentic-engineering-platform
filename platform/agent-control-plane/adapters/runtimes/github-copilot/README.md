# GitHub Copilot Runtime Adapter

This scaffold owns GitHub Copilot capability declarations, supported-version
ranges, mapping tests, and renderers when concrete runtime translation is
required.

List checked-in generated installation files, one repository-relative path per
line, in the adapter-owned `generated-installation-manifest.txt`. This manifest
supports the adapter by inventorying expected outputs; it is not itself a
translation adapter.

Canonical behavior remains under `../../../agent-assets/`. Repository-native
installation files remain under `.github/copilot-instructions.md` and the
agent-related `.github/` paths and should contain only discovery links,
canonical imports, generated files, or explicitly approved GitHub
Copilot configuration.

Other `.github/` content, such as Actions and Dependabot configuration, is
ordinary GitHub repository configuration and is outside this adapter boundary.
