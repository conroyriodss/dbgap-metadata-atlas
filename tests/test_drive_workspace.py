import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import drive_workspace as d


def nb(role='A', value=1, outputs=False):
    return d.jbytes({'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
        {'cell_type':'markdown','source':['# Documentation'],'metadata':{}},
        {'cell_type':'code','source':[f"role = '{role}'\nvalue = {value}\n"], 'metadata':{},
         'outputs':[{'output_type':'stream','name':'stdout','text':['cached']} ] if outputs else [],
         'execution_count':1 if outputs else None}]})


class FakeDrive:
    def __init__(self):
        self.items={};self.content={};self.reads=0;self.writes=0;self.moves=[];self.n=0
        self.add('root','MyDrive',None,d.FOLDER)
        self.add('data','dbgap_analysis','root',d.FOLDER)
        self.add('nbs','Notebooks','root',d.FOLDER)
    def add(self,fid,name,parent,kind='application/octet-stream',data=b'',**more):
        m={'id':fid,'name':name,'mimeType':kind,'parents':[parent] if parent else [],'trashed':False,
           'version':'1','modifiedTime':'2026-10-21T00:00:00Z','createdTime':'2026-10-01T00:00:00Z',
           'size':str(len(data)),'md5Checksum':hashlib.md5(data).hexdigest(),
           'capabilities':{'canDownload':True,'canAddChildren':True,'canMoveItemWithinDrive':True}}
        m.update(more);self.items[fid]=m;self.content[fid]=data;return copy.deepcopy(m)
    def meta(self,fid):
        self.reads+=1;return copy.deepcopy(self.items[fid])
    def children(self,fid):
        self.reads+=1;return [copy.deepcopy(m) for m in self.items.values() if fid in m.get('parents',[]) and not m.get('trashed')]
    def bytes(self,fid,limit=d.MAX_NOTEBOOK_BYTES):
        self.reads+=1
        if len(self.content[fid])>limit:raise ValueError('oversize')
        return self.content[fid]
    def create_folder(self,parent,name,kind):
        self.n+=1;self.writes+=1
        return self.add('new'+str(self.n),name,parent,d.FOLDER)
    def write_json(self,parent,name,obj,fid=None):
        self.writes+=1
        if not fid:self.n+=1;fid='new'+str(self.n)
        version=str(int(self.items.get(fid,{}).get('version','0'))+1)
        return self.add(fid,name,parent,'application/json',d.jbytes(obj),version=version)
    def move(self,fid,old,new):
        if self.items[fid]['parents']!=[old]:raise ValueError('parent mismatch')
        self.writes+=1;self.moves.append((fid,old,new));self.items[fid]['parents']=[new]
        self.items[fid]['version']=str(int(self.items[fid]['version'])+1)
        return self.meta(fid)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.drive=FakeDrive()
        for role,p in d.CANONICAL.items():
            dest=self.root/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(nb(role))
            self.drive.add(role,d.PREFERRED[role][0],'nbs','application/x-ipynb+json',nb(role))
    def tearDown(self):self.tmp.cleanup()
    def inspect(self,ids=None):
        rows=d.inventory(self.drive,{'data':'data','notebooks':'nbs'})
        selected,cs,errors,cache=d.inspect_notebooks(self.drive,rows,self.root,ids)
        return rows,selected,cs,errors,cache
    def with_copy(self, different=False):
        self.drive.add('copy','dbGaP_A_Collection_Participation_Fixed (1).ipynb','nbs','application/x-ipynb+json',nb('A',2 if different else 1,True))
        rows,s,cs,err,cache=self.inspect({'A':'A'} if different else None)
        plan=d.cleanup_plan(rows,s,cs,d.literal_dependencies(s,cache))
        return s,plan
    def archive_copy(self):
        s,plan=self.with_copy();items=d.pick_archive_items(plan,include_suggested=True)
        return d.archive_files(self.drive,items,d.archive_phrase(items),self.root/'logs',[m['id'] for m in s.values()])
    def test_role_and_numbered_copy(self):self.assertEqual(d.role_for('Copy of dbGaP_B_Participation_Replication_Analysis_Fixed(2).ipynb'),'B')
    def test_unknown_role(self):self.assertIsNone(d.role_for('My notes.ipynb'))
    def test_no_science_execution(self):
        raw=nb().replace(b'value = 1',b"raise RuntimeError('must never execute')")
        self.assertEqual(d.notebook_summary(raw)['code_cells'],1)
    def test_code_fingerprint_ignores_outputs(self):self.assertEqual(d.notebook_summary(nb())['code_sha256'],d.notebook_summary(nb(outputs=True))['code_sha256'])
    def test_code_fingerprint_detects_change(self):self.assertNotEqual(d.notebook_summary(nb())['code_sha256'],d.notebook_summary(nb(value=2))['code_sha256'])
    def test_bad_notebook(self):
        with self.assertRaises(ValueError):d.notebook_summary(b'{}')
    def test_actual_folder(self):self.assertEqual(d.actual_folder(self.drive,'data')['id'],'data')
    def test_shortcut_input(self):
        self.drive.add('sc','shared','root',d.SHORTCUT,shortcutDetails={'targetId':'data'})
        self.assertEqual(d.actual_folder(self.drive,'sc')['id'],'data')
    def test_bad_folder(self):
        with self.assertRaises(ValueError):d.actual_folder(self.drive,'https://drive.google.com/')
    def test_notebook_depth(self):
        self.drive.add('sub','sub','nbs',d.FOLDER);self.drive.add('x','notes.txt','sub',data=b'notes')
        self.assertIn('x',[m['id'] for m in d.inventory(self.drive,{'data':'data','notebooks':'nbs'})])
    def test_no_cache_traversal(self):
        self.drive.add('cache','semantic_sources','data',d.FOLDER);self.drive.add('raw','raw.csv','cache')
        self.assertNotIn('raw',[m['id'] for m in d.inventory(self.drive,{'data':'data','notebooks':'nbs'})])
    def test_no_archive_traversal(self):
        self.drive.add('arc','_dbgap_archive_2020','nbs',d.FOLDER);self.drive.add('old','01_collect.ipynb','arc',data=nb())
        self.assertNotIn('old',[m['id'] for m in d.inventory(self.drive,{'data':'data','notebooks':'nbs'})])
    def test_inventory_limit(self):
        with self.assertRaises(ValueError):d.inventory(self.drive,{'data':'data','notebooks':'nbs'},max_items=1)
    def test_select_expected(self):
        rows,s,cs,err,cache=self.inspect();self.assertFalse(err);self.assertEqual(set(s),{'A','B','C'})
    def test_identical_copy_selects_original(self):
        s,plan=self.with_copy();self.assertEqual(s['A']['id'],'A');self.assertEqual(next(p for p in plan if p['id']=='copy')['action'],'SUGGEST_ARCHIVE')
    def test_different_copy_requires_choice(self):
        self.drive.add('copy',d.PREFERRED['A'][0].replace('.ipynb','(1).ipynb'),'nbs',data=nb('A',9))
        self.assertTrue(self.inspect()[3])
    def test_wrong_explicit_role(self):self.assertTrue(self.inspect({'A':'B'})[3])
    def test_repeated_explicit_id(self):
        with self.assertRaises(ValueError):self.inspect({'A':'B','B':'B'})
    def test_outside_explicit_id(self):
        with self.assertRaises(ValueError):self.inspect({'A':'other'})
    def test_missing_current_notebook(self):
        self.drive.items['A']['name']='unrecognized.ipynb'
        self.assertTrue(self.inspect()[3])
    def test_modified_unique_preferred_warned(self):
        self.drive.content['A']=nb('A',8)
        self.assertFalse(self.inspect()[1]['A']['expected_code'])
    def test_preview_no_writes(self):
        rows,s,cs,err,cache=self.inspect();p=d.cleanup_plan(rows,s,cs);d.write_reports(self.root/'reports',rows,s,cs,err,p)
        self.assertEqual(self.drive.writes,0)
    def test_protected_data_even_duplicate(self):
        self.drive.add('tab','data (1).parquet','data');s,p=self.with_copy()
        self.assertEqual(next(x for x in p if x['id']=='tab')['action'],'KEEP')
    def test_protected_checkpoint(self):
        self.drive.add('cp','dar_fetch_checkpoint.json','data');s,p=self.with_copy()
        self.assertEqual(next(x for x in p if x['id']=='cp')['action'],'KEEP')
    def test_protected_source_dependency(self):
        self.drive.add('p','dbgap_results.html','data')
        rows,s,cs,e,c=self.inspect();p=d.cleanup_plan(rows,s,cs,{'dbgap_results.html'})
        self.assertEqual(next(x for x in p if x['id']=='p')['action'],'KEEP')
    def test_report_duplicate(self):
        self.drive.add('p','dbgap_results.html','data',data=b'report');self.drive.add('p1','dbgap_results (1).html','data',data=b'report')
        rows,s,cs,e,c=self.inspect();p=d.cleanup_plan(rows,s,cs)
        self.assertEqual(next(x for x in p if x['id']=='p1')['keeper_id'],'p')
    def test_different_report_retained(self):
        self.drive.add('p','dbgap_results.html','data',data=b'report');self.drive.add('p1','dbgap_results (1).html','data',data=b'changed')
        rows,s,cs,e,c=self.inspect();p=d.cleanup_plan(rows,s,cs)
        self.assertEqual(next(x for x in p if x['id']=='p1')['action'],'REVIEW_EXPORT')
    def test_different_notebook_review(self):
        s,p=self.with_copy(True);self.assertEqual(next(x for x in p if x['id']=='copy')['action'],'REVIEW_VERSION')
    def test_pick_protected_rejected(self):
        s,p=self.with_copy()
        with self.assertRaises(ValueError):d.pick_archive_items(p,['A'])
    def test_confirmation_required(self):
        s,p=self.with_copy();items=d.pick_archive_items(p,include_suggested=True)
        with self.assertRaises(ValueError):d.archive_files(self.drive,items,'',self.root)
        self.assertEqual(self.drive.writes,0)
    def test_changed_after_preview_rejected(self):
        s,p=self.with_copy();items=d.pick_archive_items(p,include_suggested=True);self.drive.items['copy']['version']='2'
        with self.assertRaises(ValueError):d.archive_files(self.drive,items,d.archive_phrase(items),self.root)
        self.assertEqual(self.drive.writes,0)
    def test_readonly_rejected(self):
        s,p=self.with_copy();items=d.pick_archive_items(p,include_suggested=True);self.drive.items['copy']['capabilities']['canMoveItemWithinDrive']=False
        with self.assertRaises(PermissionError):d.archive_files(self.drive,items,d.archive_phrase(items),self.root)
        self.assertEqual(self.drive.writes,0)
    def test_archive_moves_preserves_bytes(self):
        before=self.drive.content['A'];r=self.archive_copy()
        self.assertEqual(r['moved'],1);self.assertEqual(self.drive.content['A'],before);self.assertIn('copy',self.drive.items)
        self.assertTrue(self.drive.items[self.drive.items['copy']['parents'][0]]['name'].startswith('_dbgap_archive'))
    def test_private_journal_folder(self):
        r=self.archive_copy();parent=self.drive.items[r['journal_id']]['parents'][0]
        self.assertEqual(self.drive.items[parent]['parents'],['root'])
    def test_restore(self):
        r=self.archive_copy();result=d.restore_archive(self.drive,r['journal_id'],'RESTORE '+r['journal_id'],{'data','nbs'})
        self.assertEqual(result['restored'],1);self.assertEqual(self.drive.items['copy']['parents'],['nbs'])
    def test_restore_idempotent(self):
        r=self.archive_copy();d.restore_archive(self.drive,r['journal_id'],'RESTORE '+r['journal_id'],{'data','nbs'})
        self.assertEqual(d.restore_archive(self.drive,r['journal_id'],'RESTORE '+r['journal_id'],{'data','nbs'})['restored'],0)
    def test_restore_changed_content_blocks(self):
        r=self.archive_copy();self.drive.content['copy']=nb('A',99)
        with self.assertRaises(ValueError):d.restore_archive(self.drive,r['journal_id'],'RESTORE '+r['journal_id'],{'data','nbs'})
    def test_restore_outside_scope(self):
        r=self.archive_copy()
        with self.assertRaises(ValueError):d.restore_archive(self.drive,r['journal_id'],'RESTORE '+r['journal_id'],{'other'})
    def test_restore_filename_collision(self):
        r=self.archive_copy();self.drive.add('new','dbGaP_A_Collection_Participation_Fixed (1).ipynb','nbs',data=nb())
        with self.assertRaises(ValueError):d.restore_archive(self.drive,r['journal_id'],'RESTORE '+r['journal_id'],{'data','nbs'})
    def test_restore_confirmation(self):
        with self.assertRaises(ValueError):d.restore_archive(self.drive,'bad','',{'data','nbs'})
    def test_selected_notebook_recheck(self):
        s=self.inspect()[1];self.drive.items['A']['version']='4'
        with self.assertRaises(ValueError):d.selection_still_current(self.drive,s)
    def test_empty_archive_no_writes(self):
        self.assertEqual(d.archive_files(self.drive,[],'',self.root)['status'],'nothing_selected');self.assertEqual(self.drive.writes,0)
    def test_keeper_scheduled_also_rejected(self):
        self.drive.add('p','dbgap_results.html','data',data=b'report');self.drive.add('p1','dbgap_results (1).html','data',data=b'report')
        rows,s,cs,e,c=self.inspect();p=d.cleanup_plan(rows,s,cs);items=d.pick_archive_items(p,['p','p1'])
        with self.assertRaises(ValueError):d.archive_files(self.drive,items,d.archive_phrase(items),self.root)
    def test_mount_resolves_real_path(self):
        (self.root/'MyDrive/dbgap_analysis').mkdir(parents=True)
        self.assertEqual(d.mounted_path(self.drive,self.drive.meta('data'),str(self.root)),str(self.root/'MyDrive/dbgap_analysis'))
    def test_mount_ambiguous_name_not_guessed(self):
        (self.root/'MyDrive/dbgap_analysis').mkdir(parents=True);self.drive.add('data2','dbgap_analysis','root',d.FOLDER)
        self.assertIsNone(d.mounted_path(self.drive,self.drive.meta('data'),str(self.root)))
    def test_api_inventory_preserves_keys(self):
        rows=d.inventory(self.drive,{'data':'data','notebooks':'nbs'});self.assertTrue(all('id' in r and 'parents' in r for r in rows))
    def test_notebook_cache_skips_repeated_downloads(self):
        rows,s,cs,e,cache=self.inspect()
        with patch.object(self.drive,'bytes',side_effect=AssertionError('should be cached')):
            d.inspect_notebooks(self.drive,rows,self.root,cache=cache)
    def test_actual_folder_trashed(self):
        self.drive.items['data']['trashed']=True
        with self.assertRaises(ValueError):d.actual_folder(self.drive,'data')

if __name__=='__main__': unittest.main()
