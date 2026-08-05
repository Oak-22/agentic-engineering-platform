# Provider Runtime Adapters

This directory owns capability and version mappings for agent runtimes such as
Codex, Claude Code, and GitHub Copilot. Add a provider directory only with its
first concrete capability declaration or renderer.

Each adapter must identify the canonical schema versions and provider versions
it supports, render provider-native discovery or policy artifacts, and report
unsupported semantics without weakening canonical intent. Repository-root
runtime paths remain generated or linked discovery outputs rather than
canonical sources.
