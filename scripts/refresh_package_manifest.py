"""Refresh explicit public code/docs paths, notebook lineage and hashes after reviewed edits.

Use --clean-notebooks to clear outputs/editor metadata in repository notebook copies.
This never touches source data, checkpoints, or a Drive working directory.
"""
import argparse
import json
from pathlib import Path
from repo_tools import write_package_manifests, verify_package, notebook_codes, sanitize_notebook, sha256, json_bytes
root=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--clean-notebooks',action='store_true');args=p.parse_args()
    if args.clean_notebooks:
        for path in (root/'notebooks').glob('*.ipynb'):
            path.write_bytes(sanitize_notebook(path.read_bytes()))
    source=root/'provenance/source_notebooks.json'
    lineage=json.loads(source.read_text())
    for item in lineage['files']:
        path=root/item['repository_path'];data=path.read_bytes()
        adopted=item.setdefault('adopted_code_cell_sha256',item['code_cell_sha256'].copy())
        current=[sha256(c.encode()) for c in notebook_codes(data)]
        item['code_cells_unchanged']=current==adopted
        item['code_cell_sha256']=current;item['code_cells']=len(current)
        item['prepared_file_sha256']=sha256(data)
        if current!=adopted:
            item['publisher_note']='Maintainer-reviewed source update; original adopted file and code hashes retained. Not scientific validation.'
    source.write_bytes(json_bytes(lineage))
    write_package_manifests(root)
    print(verify_package(root))
