import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import drive_workspace as d
import repo_tools as r
import publish_github as pub
from test_drive_workspace import FakeDrive
ROOT=Path(__file__).resolve().parents[1]

class ActualNotebookStagingTests(unittest.TestCase):
    def run_stage(self,output=False):
        drive=FakeDrive()
        for role,path in d.CANONICAL.items():
            raw=(ROOT/path).read_bytes()
            if output:
                nb=json.loads(raw)
                next(c for c in nb['cells'] if c['cell_type']=='code')['outputs']=[{'output_type':'stream','name':'stdout','text':['private execution output']}]
                raw=d.jbytes(nb)
            drive.add('private-selected-'+role,d.PREFERRED[role][0],'nbs','application/x-ipynb+json',raw)
        rows=d.inventory(drive,{'data':'data','notebooks':'nbs'})
        sel,cs,err,cache=d.inspect_notebooks(drive,rows,ROOT)
        self.assertEqual(err,[])
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        stage=d.stage_notebooks(ROOT,Path(temp.name)/'stage',sel,cache)
        payload=pub.build_payload(stage,'example','atlas')
        return drive,stage,payload,sel
    def test_actual_code_cells_unchanged(self):
        dr,st,p,s=self.run_stage(True)
        count=0
        for role,name in d.CANONICAL.items():
            self.assertEqual(r.notebook_codes((ROOT/name).read_bytes()),r.notebook_codes(p[name]))
            self.assertFalse(any(c.get('outputs') for c in json.loads(p[name])['cells']))
            count+=len(r.notebook_codes(p[name]))
        self.assertEqual(count,47);self.assertEqual(dr.writes,0)
    def test_private_drive_ids_not_in_public_provenance(self):
        dr,st,p,s=self.run_stage()
        for name,raw in p.items():
            if name.startswith('provenance/'):
                self.assertNotIn(b'private-selected-',raw)
        self.assertNotIn('drive_inventory.json',p)
    def test_execution_outputs_do_not_change_public_payload(self):
        a=self.run_stage(False)[2];b=self.run_stage(True)[2]
        self.assertEqual(pub.payload_fingerprint(a),pub.payload_fingerprint(b))
    def test_prepared_package_verifies(self):
        dr,st,p,s=self.run_stage()
        self.assertEqual(r.verify_package(st)['scan'],'pass')
    def test_forbid_public_drive_id_setting(self):
        with self.assertRaises(ValueError):
            d.stage_notebooks(ROOT,ROOT,{}, {},source_ids_public=True)
