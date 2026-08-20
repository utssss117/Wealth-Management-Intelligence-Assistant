import json

with open('clean_nav_data.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']
print(f'Total cells: {len(cells)}')
for i, cell in enumerate(cells):
    if cell['cell_type'] == 'code':
        exec_count = cell.get('execution_count')
        source = ''.join(cell['source'])[:300]
        has_output = bool(cell['outputs'])
        print(f'--- Cell {i+1} (exec_count={exec_count}) ---')
        print(f'SOURCE: {source}')
        print(f'HAS OUTPUT: {has_output}')
        print()
