---
migration_id: folder-structure-visualizer-into-control-plane-tools
status: complete
source_project: folder_structure_visualizer
target_path: tools/folder_structure_visualizer
component_role: optional_reference_tool
package_independence: required
runtime_dependency_of_control_plane: false
---

# Folder Structure Visualizer relocation contract

## Product positioning

Build infrastructure for reliable agentic engineering that increases
software-delivery velocity without sacrificing human understanding,
organizational memory, or operational control.

Agentic engineering is the larger technical and commercial surface.
Developer competence is a critical system property of that surface, not
the entire product category.

## Migration objective

Relocate `folder_structure_visualizer` into
`tools/folder_structure_visualizer/` as the first independently
packageable reference tool supporting the Agent Instruction Control
Plane.

The tool provides a semantic repository-orientation surface for humans
and agents. It maps structural hierarchy and attaches durable,
reviewable descriptions of component responsibility.

## Ownership boundary

The control plane owns:

- agent context and instruction-governance contracts
- integration guidance for semantic repository maps
- knowledge-capture and promotion workflows
- optional reference-tool orchestration

The Folder Structure Visualizer owns:

- filesystem scanning and filtering
- shared tree-node representation
- semantic annotation attachment and completeness reporting
- text, Markdown, Mermaid, SVG, PNG, and HTML rendering
- its Python package, CLI, tests, and release lifecycle

The tool must remain usable independently. The control plane must remain
usable without installing the tool.

## Migration invariants

1. Preserve `folderviz` as the console-command name.
2. Preserve the package's own `pyproject.toml`, `src/`, `tests/`,
   `examples/`, and README.
3. Preserve deterministic rendering without requiring an LLM at runtime.
4. Keep semantic annotations as explicit, reviewable input artifacts.
5. Do not migrate virtual environments, caches, generated package
   metadata, or machine-specific personal symlinks.
6. Do not make private knowledge-base paths part of the public package.
7. Do not modify unrelated control-plane work during relocation.

## Excluded source artifacts

- `.venv/`
- `.pytest_cache/`
- `**/__pycache__/`
- `src/*.egg-info/`
- `engineering_knowledge_base`

These are local runtime, cache, generated metadata, or personal overlay
artifacts rather than portable source.

## Validation contract

The relocation is complete only when:

- [x] the target exists at `tools/folder_structure_visualizer/`
- [x] all Python tests pass from the target directory
- [x] `python -m folder_structure_visualizer --help` succeeds from the
      target environment
- [x] sample annotated tree generation succeeds
- [x] excluded local artifacts are absent from the target
- [x] the former sibling working directory is retired recoverably
- [x] this document's status is changed to `complete`

## Completion record

- Tests: `22 passed`
- CLI validation: `python -m folder_structure_visualizer --help`
- Sample validation: annotated text, Markdown, and Mermaid generation
- Former sibling working directory moved to a local recoverable backup
  outside the repository; its machine-local path is intentionally not
  part of the portable migration contract.

## Future boundary

Automatic annotation generation is not part of this relocation.
A future opt-in semantic indexing command may use a lightweight local
model to propose incremental annotation changes. Deterministic rendering
must remain separate from model-assisted annotation generation.
