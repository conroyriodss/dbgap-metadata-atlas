"""Regression tests for project-only notebook budgets. All Drive calls are fake."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import drive_workspace as d
import test_drive_workspace as helpers
nb = helpers.nb


class LargeFolderTests(unittest.TestCase):
    setUp = helpers.WorkspaceTests.setUp
    tearDown = helpers.WorkspaceTests.tearDown
    inspect = helpers.WorkspaceTests.inspect

    def many_unrelated(self, n=1000):
        for i in range(n):
            self.drive.add('unrelated'+str(i), f'Other project {i}.ipynb', 'nbs', data=b'not read')

    def many_preferred(self, n=180):
        for i in range(n):
            name=d.PREFERRED['A'][0].replace('.ipynb',f' ({i+1}).ipynb')
            self.drive.add('copy'+str(i),name,'nbs',data=nb('A'))

    def test_1000_unrelated_notebooks_do_not_trigger_project_cap(self):
        self.many_unrelated()
        with patch.object(self.drive,'bytes', wraps=self.drive.bytes) as call:
            rows,sel,candidates,errors,cache=self.inspect()
        self.assertEqual(errors,[])
        self.assertEqual(set(sel),{'A','B','C'})
        self.assertEqual({x.args[0] for x in call.call_args_list},{'A','B','C'})
        self.assertEqual(d.inspection_stats(rows,candidates)['unrelated_notebooks_not_read'],1000)
        self.assertEqual(self.drive.writes,0)

    def test_150_unrelated_boundary_not_a_failure(self):
        self.many_unrelated(150)
        self.assertEqual(self.inspect()[3],[])

    def test_unrelated_case_insensitive_extensions_counted_not_read(self):
        self.drive.add('UPPER','Unrelated.IPYNB','nbs',data=b'invalid')
        rows,sel,cs,e,c=self.inspect()
        self.assertFalse(e)
        self.assertEqual(d.inspection_stats(rows,cs)['unrelated_notebooks_not_read'],1)

    def test_explicit_ids_with_many_unrelated(self):
        self.many_unrelated()
        for r in ['A','B','C']:self.drive.items[r]['name']=f'Chosen {r}.ipynb'
        rows,s,cs,e,c=self.inspect({'A':'A','B':'B','C':'C'})
        self.assertEqual(e,[])
        self.assertTrue(all(x['expected_code'] for x in s.values()))

    def test_too_many_current_candidates_return_informative_errors_not_exception(self):
        self.many_preferred()
        rows,s,cs,e,c=self.inspect()
        self.assertNotIn('A',s)
        self.assertEqual(set(s),{'B','C'})
        self.assertTrue(any('competing candidates' in x for x in e))
        self.assertTrue(any(x.get('inspection_deferred') for x in cs))
        self.assertEqual(self.drive.writes,0)

    def test_explicit_ids_have_priority_even_with_180_current_copies(self):
        self.many_preferred()
        with patch.object(self.drive,'bytes', wraps=self.drive.bytes) as call:
            rows,s,cs,e,c=self.inspect({'A':'A','B':'B','C':'C'})
        self.assertEqual(e,[])
        self.assertEqual([x.args[0] for x in call.call_args_list[:3]],['A','B','C'])
        self.assertLessEqual(call.call_count,150)
        self.assertEqual(len(cs),183)

    def test_deferred_project_notebooks_are_not_archive_candidates(self):
        self.many_preferred()
        rows,s,cs,e,c=self.inspect({'A':'A','B':'B','C':'C'})
        deferred={x['id'] for x in cs if x.get('inspection_deferred')}
        self.assertTrue(deferred)
        plan=d.cleanup_plan(rows,s,cs)
        self.assertTrue(all(p['action']=='KEEP' for p in plan if p['id'] in deferred))

    def test_different_copy_not_silently_selected(self):
        self.drive.add('changed',d.PREFERRED['A'][0].replace('.ipynb',' (1).ipynb'),'nbs',data=nb('A',2))
        rows,s,cs,e,c=self.inspect()
        self.assertNotIn('A',s)
        self.assertTrue(any('multiple different' in x for x in e))

    def test_preferred_current_selection_precedes_old_versions(self):
        for i in range(200):
            self.drive.add(f'old{i}',f'dbGaP_A_old_{i}.ipynb','nbs',data=nb('A',i+3))
        rows,s,cs,e,c=self.inspect()
        self.assertEqual(e,[])
        self.assertEqual(s['A']['id'],'A')
        self.assertTrue(any(x.get('inspection_deferred') for x in cs))

    def test_candidate_csv_includes_deferred_ids(self):
        self.many_preferred()
        rows,s,cs,e,c=self.inspect()
        out=d.write_reports(self.root/'reports',rows,s,cs,e,[])
        text=(out/'notebook_candidates.csv').read_text()
        self.assertIn('deferred',text)
        self.assertIn('copy179',text)
        self.assertEqual(self.drive.writes,0)

    def test_permission_error_becomes_review_error(self):
        original=self.drive.bytes
        def download(fid,*args,**kwargs):
            if fid=='A':raise PermissionError('no download permission')
            return original(fid,*args,**kwargs)
        with patch.object(self.drive,'bytes',side_effect=download):
            rows,s,cs,e,c=self.inspect()
        self.assertNotIn('A',s)
        self.assertIn('B',s)
        self.assertTrue(any('PermissionError' in x.get('inspection_error','') for x in cs))

    def test_changed_content_during_inspection_is_withheld(self):
        original=self.drive.bytes
        def download(fid,*args,**kwargs):
            raw=original(fid,*args,**kwargs)
            if fid=='A':self.drive.items[fid]['version']='2'
            return raw
        with patch.object(self.drive,'bytes',side_effect=download):
            rows,s,cs,e,c=self.inspect()
        self.assertNotIn('A',s)
        self.assertTrue(e)

    def test_oversized_notebook_is_withheld(self):
        with patch.object(self.drive,'bytes',side_effect=ValueError('oversize')):
            rows,s,cs,e,c=self.inspect()
        self.assertFalse(s)
        self.assertEqual(len(e),3)

    def test_invalid_role_key_rejected(self):
        with self.assertRaises(ValueError):self.inspect({'D':'A'})

    def test_folder_cannot_be_an_explicit_notebook(self):
        self.drive.add('sub','sub.ipynb','nbs',d.FOLDER)
        with self.assertRaises(ValueError):self.inspect({'A':'sub'})

    def test_empty_project_folder_returns_missing_roles(self):
        for r in ['A','B','C']:self.drive.items[r]['name']=f'Unrelated {r}.ipynb'
        rows,s,cs,e,c=self.inspect()
        self.assertFalse(s)
        self.assertEqual(cs,[])
        self.assertEqual(len(e),3)

    def test_repeated_inspection_uses_cache(self):
        self.many_unrelated()
        rows,s,cs,e,c=self.inspect()
        with patch.object(self.drive,'bytes',side_effect=AssertionError('no repeated download')):
            s2,cs2,e2,c2=d.inspect_notebooks(self.drive,rows,self.root,cache=c)
        self.assertEqual(e2,[])

    def test_selection_settings_signature_changes_on_selection_or_folder_change(self):
        a=d.inventory_request('data','nbs',{},2,150)
        self.assertNotEqual(a,d.inventory_request('data','nbs',{'A':'A'},2,150))
        self.assertNotEqual(a,d.inventory_request('data','other',{},2,150))
        self.assertEqual(a,d.inventory_request('data','nbs',{},2,150))

    def test_invalid_budget_rejected(self):
        rows=d.inventory(self.drive,{'data':'data','notebooks':'nbs'})
        for value in [0,2,None,False,-1]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                d.inspect_notebooks(self.drive,rows,self.root,max_candidates=value)

    def test_explicit_small_budget_reads_three_notebooks(self):
        self.many_preferred()
        rows=d.inventory(self.drive,{'data':'data','notebooks':'nbs'})
        with patch.object(self.drive,'bytes',wraps=self.drive.bytes) as call:
            s,cs,e,c=d.inspect_notebooks(self.drive,rows,self.root,{'A':'A','B':'B','C':'C'},max_candidates=3)
        self.assertEqual(e,[])
        self.assertEqual(call.call_count,3)

if __name__=='__main__':unittest.main()
