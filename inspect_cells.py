# Quick script to peek inside a .ipynb without opening Jupyter.
# Prints each code cell's source and whether it has output.

import json

NOTEBOOK_PATH = "clean_nav_data.ipynb"

with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
    notebook = json.load(f)

cells = notebook["cells"]
print(f"Total cells: {len(cells)}\n")

for i, cell in enumerate(cells):
    if cell["cell_type"] != "code":
        continue

    exec_count = cell.get("execution_count")
    source     = "".join(cell["source"])[:300]  # first 300 chars is enough
    has_output = bool(cell["outputs"])

    print(f"--- Cell {i + 1}  (exec #{exec_count}) ---")
    print(source)
    print(f"has output: {has_output}\n")
