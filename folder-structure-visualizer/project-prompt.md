Build a production-quality Python mini project called folder_structure_visualizer.

Goal:
Create a local CLI tool that scans a root directory and generates a living visual map of the folder structure beneath it. The tool should support plain-text tree output, Markdown output, Mermaid diagram output, and optional PNG/SVG rendering. It should be useful for documenting real business/project folders like ~/Documents/__JB Photography.

Core requirements:
1. Accept any root directory as input.
2. Recursively walk folders beneath that root.
3. Generate a readable tree view.
4. Generate a Markdown document containing the folder tree.
5. Generate a Mermaid diagram representing the same folder structure.
6. Optionally render the Mermaid diagram to SVG/PNG if the required renderer is available.
7. Allow the user to limit depth.
8. Allow the user to ignore hidden files/folders.
9. Allow the user to ignore archive folders.
10. Allow the user to ignore common system folders.
11. Allow output files to be written into a chosen output directory.
12. Include a clean README with setup, usage examples, and sample outputs.

Recommended tech stack:
- Python 3.11+
- Standard library where possible
- pathlib for filesystem paths
- argparse or typer for CLI
- dataclasses for internal tree node representation
- pytest for tests
- Optional: rich for prettier terminal output
- Optional: Mermaid CLI (mmdc) for rendering Mermaid to SVG/PNG

Project structure:
folder_structure_visualizer/
├── README.md
├── pyproject.toml
├── src/
│   └── folder_structure_visualizer/
│       ├── init.py
│       ├── cli.py
│       ├── scanner.py
│       ├── models.py
│       ├── render_tree.py
│       ├── render_markdown.py
│       ├── render_mermaid.py
│       └── render_image.py
├── tests/
│   ├── test_scanner.py
│   ├── test_render_tree.py
│   ├── test_render_markdown.py
│   └── test_render_mermaid.py
└── examples/
    ├── sample_structure.md
    └── sample_structure.mmd

CLI behavior:
The main command should be:

python -m folder_structure_visualizer --root "/path/to/folder"

Support these flags:

--root
Required. The directory to scan.

--output-dir
Optional. Directory where generated files should be written. Default: current working directory.

--name
Optional. Human-readable project name for the generated document title. Default: root folder name.

--max-depth
Optional integer. Limits recursion depth. Example: --max-depth 3.

--include-files
Optional boolean flag. By default, only folders are included. If enabled, files are included too.

--ignore-hidden
Default true. Ignore files/folders starting with ".".

--ignore-archives
Default true. Ignore folders whose names include archive-like terms.

Archive folder matching should include:
- archive
- archives
- archived
- old
- backup
- backups
- deprecated
- zz archive
- 99 archive

--ignore
Optional repeatable argument for custom ignore patterns.
Example:
--ignore "node_modules" --ignore "pycache" --ignore ".git"

--formats
Optional comma-separated list. Default: tree,markdown,mermaid.
Allowed:
- tree
- markdown
- mermaid
- svg
- png

Example:
--formats tree,markdown,mermaid,svg

--color-by-depth
Optional flag. In Mermaid output, apply different classes/colors by folder depth.

--watch
Optional stretch goal. Watch the directory for changes and regenerate outputs automatically.

Output files:
If the root folder is __JB Photography, generate:

structure.txt
structure.md
structure.mmd
structure.svg
structure.png

Markdown output:
The Markdown output should look like:

# Folder Structure: __JB Photography

Generated: YYYY-MM-DD HH:MM

Root:
/Users/julian/Documents/__JB Photography

## Tree

text __JB Photography ├── 00 Inbox ├── 01 Branding │   ├── Logo Design │   └── Brand Assets ├── 02 Marketing │   ├── Advertising │   └── Google Business Profile └── zz Archive 

## Mermaid Diagram

mermaid graph TD     node_0["__JB Photography"]     node_1["00 Inbox"]     node_2["01 Branding"]     node_3["Logo Design"]     node_4["Brand Assets"]      node_0 --> node_1     node_0 --> node_2     node_2 --> node_3     node_2 --> node_4 

Tree output rules:
- Use standard tree characters:
  - ├──
  - └──
  - │
- Sort folders alphabetically by default.
- Put folders before files if files are included.
- Respect Finder-style naming conventions such as:
  - 00 Inbox
  - 01 Branding
  - 02 Marketing
  - zz Archive

Mermaid output rules:
- Use graph TD.
- Use stable node IDs like node_0, node_1, etc.
- Escape quotes and special characters safely.
- Folder labels should preserve original folder names.
- If --color-by-depth is enabled, assign Mermaid classes by depth:
  - depth0
  - depth1
  - depth2
  - depth3
  - depth4plus
- Include class definitions at the bottom.
- Do not generate invalid Mermaid if folder names contain spaces, punctuation, ampersands, slashes, apostrophes, parentheses, or emojis.

Internal design:
Create a TreeNode dataclass:

@dataclass
class TreeNode:
    name: str
    path: Path
    is_dir: bool
    depth: int
    children: list["TreeNode"]

Scanner responsibilities:
- Validate root exists.
- Validate root is a directory.
- Recursively scan children.
- Apply ignore rules.
- Respect max depth.
- Return a TreeNode root.

Renderer responsibilities:
- render_tree(root: TreeNode) -> str
- render_markdown(root: TreeNode, metadata: dict) -> str
- render_mermaid(root: TreeNode, color_by_depth: bool = False) -> str

Image rendering:
Implement a function that attempts to call Mermaid CLI if installed:

mmdc -i structure.mmd -o structure.svg
mmdc -i structure.mmd -o structure.png

If Mermaid CLI is not installed, do not crash. Print a helpful warning:
"Mermaid CLI not found. Install it with: npm install -g @mermaid-js/mermaid-cli"

Error handling:
- If root path does not exist, show a clean error.
- If root is not a directory, show a clean error.
- If output directory does not exist, create it.
- If permission errors occur while scanning, skip inaccessible folders and record a warning.
- The tool should not crash on weird folder names.

Testing:
Create tests using temporary directories.

Test cases:
1. Scans a simple nested folder structure.
2. Respects max depth.
3. Ignores hidden folders.
4. Ignores archive folders.
5. Includes files only when --include-files is passed.
6. Mermaid output contains valid node IDs and edges.
7. Markdown output includes title, root path, tree, and Mermaid block.
8. Special characters in folder names are escaped safely.

README should include:
- What the tool does
- Why it exists
- Installation instructions
- Usage examples
- Example output
- Optional Mermaid rendering setup
- Recommended folder workflow

Example usage commands:

python -m folder_structure_visualizer --root "/Documents/__JB Photography"

python -m folder_structure_visualizer 
  --root "/Documents/__JB Photography" 
  --output-dir "/Documents/__JB Photography/00 Inbox" 
  --max-depth 3 
  --formats tree,markdown,mermaid

python -m folder_structure_visualizer 
  --root "/Documents/__JB Photography" 
  --formats markdown,mermaid,svg 
  --color-by-depth

Quality requirements:
- Code should be clean, typed, and readable.
- Use meaningful function names.
- Avoid overengineering.
- Prioritize a working CLI.
- Include comments where logic is non-obvious.
- Keep dependencies minimal.
- The project should run locally on macOS.

Stretch goals:
1. Add --watch mode using watchdog to regenerate outputs when folders change.
2. Add --open flag to open the generated Markdown or SVG after export.
3. Add JSON export.
4. Add a config file .folderviz.toml for reusable settings.
5. Add option to hide empty folders.
6. Add option to collapse folders deeper than N levels.
7. Add option to generate a root-level STRUCTURE.md inside the scanned folder.

Definition of done:
The project is complete when I can run:

python -m folder_structure_visualizer --root "~/Documents/__JB Photography" --max-depth 3 --formats tree,markdown,mermaid

and it generates:
- structure.txt
- structure.md
- structure.mmd

with an accurate representation of the folder structure.	
