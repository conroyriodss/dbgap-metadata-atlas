"""Execute the actual B/C notebooks on synthetic CSV inputs, with network blocked.

Overrides test-only settings in memory. Does not save altered canonical notebook source.
"""
from __future__ import annotations
import argparse
import ast
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import csv
import hashlib
import json
from pathlib import Path
import socket
import sys
import time


@contextmanager
def no_network():
    old=socket.socket.connect
    def blocked(*args,**kwargs):
        raise RuntimeError('Network use is blocked in the synthetic smoke test.')
    socket.socket.connect=blocked
    try:yield
    finally:socket.socket.connect=old


def write_csv(path,fields,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def make_fixture(path):
    path.mkdir(parents=True,exist_ok=False)
    ids=[f'phs990000{i}' for i in range(1,9)]
    roots=[];dar=[];links=[];pubmed=[];icite=[]
    for i,r in enumerate(ids,1):
        n=i%4;npubs=i%3
        roots.append({'root_accession':r,'latest_accession':r+'.v1.p1','n_dar_total':n,
                      'n_publications':npubs,'n_subjects_total':10*i,'num_variables':i*3,
                      'mesh_terms':'[]','data_types':'["RNA-Seq"]' if i%2 else '["WGS"]',
                      'study_name':f'SYNTHETIC TEST STUDY {i}','publications_fetch_note':'ok'})
        for j in range(n):
            dar.append({'queried_accession':r+'.v1.p1','wlid':f'SYNTHETIC-{j+1}',
                        'fname':'Synthetic','lname':f'Accessor{j+1}',
                        'org_name':f'SYNTHETIC Institution {j%2+1}',
                        'initial_approval_date':f'{2010+i}-05-01','status':'approved'})
        for j in range(npubs):
            pmid=str(99000000+i*10+j)
            row={'pmid':pmid,'pubmed_title':f'SYNTHETIC TEST PAPER {i}-{j}',
                 'pubmed_pub_date':f'{2011+i}-06-01','pubmed_fetch_note':'ok'}
            links.append({'root_accession':r,**row});pubmed.append(row)
            icite.append({'pmid':pmid,'rcr':float(j),'icite_fetch_note':'ok','citation_count':j+1,'icite_year':2011+i})
    write_csv(path/'joined_accessions_dar.csv',list(roots[0]),roots)
    write_csv(path/'dar_records.csv',list(dar[0]),dar)
    write_csv(path/'dbgap_study_pubmed_links_full.csv',list(links[0]),links)
    write_csv(path/'pubmed_metadata_full.csv',list(pubmed[0]),pubmed)
    write_csv(path/'icite_rcr_metrics.csv',list(icite[0]),icite)
    write_csv(path/'dbgap_first_observed_ledger.csv',['root_accession','first_observed_utc'],
              [{'root_accession':r,'first_observed_utc':f'{2010+i}-01-01'} for i,r in enumerate(ids)])


class SettingsOverride(ast.NodeTransformer):
    def __init__(self,settings):self.settings=settings
    def visit_Assign(self,node):
        if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in self.settings:
            node.value=ast.Constant(self.settings[node.targets[0].id])
        return node


def run_notebook(path,settings):
    nb=json.loads(path.read_text());scope={'__name__':'__main__'};cells=0
    for i,cell in enumerate(nb['cells']):
        if cell['cell_type']!='code':continue
        tree=ast.parse(''.join(cell['source']),filename=f'{path.name}:{i}')
        tree=SettingsOverride(settings).visit(tree);ast.fix_missing_locations(tree)
        print('Executing',path.name,'cell',i,flush=True)
        exec(compile(tree,f'{path.name}:{i}','exec'),scope)
        cells+=1
    return cells


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--powerpoint',action='store_true')
    args=p.parse_args();dest=args.output.resolve()
    if dest.exists():raise FileExistsError('Use a new synthetic output directory; never an existing data workspace.')
    root=Path(__file__).resolve().parents[1]
    if dest.is_relative_to(root):raise ValueError('Synthetic outputs must remain outside the code repository.')
    dest.mkdir(parents=True);data=dest/'synthetic_data';make_fixture(data)
    original={p.name:digest(p) for p in data.iterdir() if p.is_file()}
    settings={'DRIVE_ROOT':str(data),'SHOW_FIGURES':False,'INSTALL_MISSING':False,'MOUNT_DRIVE':False,
              'OUTPUT_LABEL':'SYNTHETIC SOFTWARE TEST - NOT EMPIRICAL RESULTS','MODEL_ENABLED':False,
              'BUILD_INTERACTIVE_EXPLORER':False,'DOWNLOAD_HTML':False,'DOWNLOAD_IN_COLAB':False,
              'EXPORT_POWERPOINT':args.powerpoint,'ACCESSION_DATE_BASIS':'local_first_observed'}
    start=time.time()
    with (dest/'execution.log').open('w') as log,redirect_stdout(log),redirect_stderr(log),no_network():
        b=run_notebook(root/'notebooks/02_analyze.ipynb',settings)
        c=run_notebook(root/'notebooks/03_slides.ipynb',settings)
    assert all(digest(data/n)==h for n,h in original.items()),'Input mutation detected.'
    htmls=list((data/'preliminary14_decks').rglob('*.html'))
    decks=[p for p in htmls if 'class="slide ' in p.read_text()]
    assert len(decks)==1,'Expected one rendered slide deck.'
    rendered=decks[0].read_text();count=rendered.count('class="slide ')
    assert count==14,f'Unexpected slide count {count}'
    assert 'SYNTHETIC' in rendered,'Synthetic output must be visibly labeled.'
    report={'status':'pass','scope':'Executed actual B and C code on synthetic CSV inputs, settings overridden in memory.',
            'B_code_cells':b,'C_code_cells':c,'slides':count,'source_inputs_unchanged':True,
            'scientific_api_calls':0,'parquet_serialization_tested':False,'powerpoint_created':bool(args.powerpoint),
            'seconds':round(time.time()-start,2),'limitations':['A collection not executed','No production records','No independent scientific validation']}
    (dest/'smoke_test_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
