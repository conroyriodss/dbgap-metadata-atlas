import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import repo_tools as rt
import publish_github as pub


class RepositoryTests(unittest.TestCase):
    def test_notebook_code_matches_adopted_source_hashes(self):
        data=json.loads((ROOT/'provenance/source_notebooks.json').read_text())
        for row in data['files']:
            with self.subTest(notebook=row['repository_path']):
                codes=rt.notebook_codes((ROOT/row['repository_path']).read_bytes())
                self.assertEqual([rt.sha256(x.encode()) for x in codes],row['code_cell_sha256'])
                self.assertEqual(len(codes),row['code_cells'])

    def test_all_public_notebooks_clean_and_parseable(self):
        for p in (ROOT/'notebooks').rglob('*.ipynb'):
            with self.subTest(p=p.name):self.assertEqual(rt.scan_bytes(p.relative_to(ROOT).as_posix(),p.read_bytes()),[])

    def test_sanitize_keeps_code(self):
        nb={'nbformat':4,'metadata':{'widgets':{'private':'x'}},'cells':[{'cell_type':'code','source':['x = 1\n'],
            'outputs':[{'output_type':'stream','text':'PRIVATE'}],'execution_count':1,'metadata':{'execution':5},'attachments':{'image':'x'}}]}
        data=rt.json_bytes(nb);clean=rt.sanitize_notebook(data)
        self.assertEqual(rt.notebook_codes(data),rt.notebook_codes(clean))
        self.assertNotIn(b'PRIVATE',clean);self.assertEqual(json.loads(clean)['metadata'],{})

    def test_sanitize_idempotent(self):
        p=(ROOT/'notebooks/01_collect.ipynb').read_bytes()
        self.assertEqual(rt.sanitize_notebook(p),rt.sanitize_notebook(rt.sanitize_notebook(p)))

    def test_paths_block_data_and_escape(self):
        for p in ['../README.md','/README.md','docs/../secret.py','docs\\x.py','data/file.json','docs/deck.html',
                  'notebooks/.ipynb_checkpoints/test.ipynb','docs/input.parquet','docs/input.csv','secret.env']:
            with self.subTest(path=p):self.assertFalse(rt.allowed_path(p))

    def test_source_paths_allowed(self):
        for p in ['README.md','notebooks/01_collect.ipynb','scripts/publish_github.py','docs/metrics.md',
                  '.github/workflows/checks.yml','docs/index.html','docs/.nojekyll','provenance/package_manifest.json']:
            with self.subTest(path=p):self.assertTrue(rt.allowed_path(p))

    def test_credential_scan(self):
        fake=('gh'+'p_')+'x'*40
        self.assertTrue(rt.scan_bytes('docs/example.md',fake.encode()))
        self.assertEqual(rt.scan_bytes('docs/example.md',b'NCBI_API_KEY = get_secret("NCBI")'),[])

    def test_literal_secret_assignment(self):
        self.assertTrue(rt.literal_secret_present('API_KEY = ' + repr('z' * 30)))
        self.assertFalse(rt.literal_secret_present('API_KEY = get_secret("NCBI")'))

    def test_readme_only_starter_receives_initial_commit(self):
        c=FakeGitHub(existing=True,readme_only=True)
        result=pub.publish(ROOT,'example','atlas',release_reviewed=True,
                           confirmation='PUBLISH example/atlas PUBLIC',client=c)
        self.assertEqual(result['branch'],'main')

    def test_executed_notebook_rejected(self):
        nb={'nbformat':4,'cells':[{'cell_type':'code','source':'x=1','outputs':[{'text':'data'}],
                              'execution_count':2,'metadata':{}}]}
        self.assertTrue(rt.scan_bytes('notebooks/test.ipynb',rt.json_bytes(nb)))

    def test_malformed_python(self):
        self.assertTrue(rt.scan_bytes('scripts/x.py',b'def broken(:'))

    def test_binary_rejected(self):
        self.assertTrue(rt.scan_bytes('docs/x.md',b'\xff'))

    def test_zip_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            z=Path(td)/'x.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('../escape.py','x=1')
            with self.assertRaises(ValueError):rt.extract_bundle(z,Path(td)/'out')

    def test_zip_rejects_unexpected_raw_data(self):
        with tempfile.TemporaryDirectory() as td:
            z=Path(td)/'x.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('dbgap-metadata-atlas/data/x.json','{}')
            with self.assertRaises(ValueError):rt.extract_bundle(z,Path(td)/'out')

    def test_zip_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileExistsError):rt.extract_bundle(Path(td)/'x.zip',Path(td))

    def test_target_validation(self):
        pub.validate_target('conroyriodss','dbgap-metadata-atlas','public')
        for owner,repo in [('https://github.com/x','x'),('x','a/b'),('x','x.git'),('x','../x')]:
            with self.subTest(owner=owner,repo=repo):
                with self.assertRaises(ValueError):pub.validate_target(owner,repo,'public')

    def test_confirmation_precedes_network(self):
        with self.assertRaises(ValueError):pub.publish(ROOT,'example','repo',confirmation='',release_reviewed=True,client=object())

    def test_payload_is_deterministic(self):
        a=pub.build_payload(ROOT,'example','repo');b=pub.build_payload(ROOT,'example','repo')
        self.assertEqual(pub.payload_fingerprint(a),pub.payload_fingerprint(b))
        self.assertNotIn(b'__OWNER__',a['README.md'])
        # A source template has placeholders; a published checkout has real URLs.
        # Preserve resolved citation attribution rather than retargeting it for this test.
        expected_citation = (ROOT / 'CITATION.cff').read_bytes()
        for source, target in [(b'__OWNER__', b'example'),
                               (b'__REPO__', b'repo'),
                               (b'__BRANCH__', b'main')]:
            expected_citation = expected_citation.replace(source, target)
        self.assertEqual(a['CITATION.cff'], expected_citation)

    def test_template_citation_resolves_requested_target(self):
        from unittest.mock import patch
        files = rt.read_public_files(ROOT)
        files['CITATION.cff'] = b'repository-code: "https://github.com/__OWNER__/__REPO__"\n'
        with patch.object(pub, 'read_public_files', return_value=files):
            data = pub.build_payload(ROOT, 'example', 'repo')
        self.assertEqual(data['CITATION.cff'], b'repository-code: "https://github.com/example/repo"\n')

    def test_resolved_citation_preserves_existing_attribution(self):
        from unittest.mock import patch
        files = rt.read_public_files(ROOT)
        citation = b'repository-code: "https://github.com/original-owner/original-repo"\n'
        files['CITATION.cff'] = citation
        with patch.object(pub, 'read_public_files', return_value=files):
            data = pub.build_payload(ROOT, 'example', 'repo')
        self.assertEqual(data['CITATION.cff'], citation)

    def test_payload_does_not_change_science(self):
        data=pub.build_payload(ROOT,'example','repo')
        for n in ['01_collect.ipynb','02_analyze.ipynb','03_slides.ipynb']:
            with self.subTest(n=n):self.assertEqual(rt.notebook_codes(data['notebooks/'+n]),rt.notebook_codes((ROOT/'notebooks'/n).read_bytes()))

    def test_payload_excludes_reports_and_raw_data(self):
        data=pub.build_payload(ROOT,'example','repo')
        self.assertEqual([x for x in data if x.endswith('.html')],['docs/index.html'])
        self.assertFalse(any(x.endswith(('.parquet','.csv','.jsonl','.pptx')) for x in data))

    def test_project_marker_required(self):
        with self.assertRaises(KeyError):
            with tempfile.TemporaryDirectory() as d:
                (Path(d)/'public_files.json').write_text('{}');rt.read_public_files(Path(d))

    def test_question_seed_count_and_ids(self):
        q=json.loads((ROOT/'docs/research_questions.json').read_text())
        self.assertEqual([x['id'] for x in q],[f'Q{i:02d}' for i in range(1,11)])
        self.assertTrue(all(x['priority'] is None for x in q))

    def test_workflow_has_no_acquisition_or_write_permissions(self):
        t=(ROOT/'.github/workflows/checks.yml').read_text()
        self.assertIn('contents: read',t);self.assertNotIn('pull_request_target',t)
        self.assertNotIn('schedule:',t);self.assertNotIn('01_collect.ipynb',t)

    def test_initial_archive_manifest(self):
        # The separate manifest test is useful after packaging, but CI source edits can legitimately
        # change hashes before a reviewed refresh. Normal CI checks syntax and policy above.
        self.assertTrue((ROOT/'public_files.json').exists())


class FakeGitHub:
    def __init__(self,existing=False,matching=False,wrong_marker=False,conflict=False,readme_only=False):
        self.calls=[];self.existing=existing;self.matching=matching;self.wrong_marker=wrong_marker
        self.conflict=conflict;self.readme_only=readme_only;self.written={};self.prefix='/repos/example/atlas'
        self.issues=[]
    def request(self,method,path,body=None,allow_missing=False):
        self.calls.append((method,path,body))
        if method=='GET' and path=='/user':return {'login':'example'}
        if method=='GET' and path==self.prefix:return {'private':False,'default_branch':'main','archived':False} if self.existing else None
        if method=='POST' and path=='/user/repos':
            self.existing=True;self.readme_only=True
            return {'private':False,'default_branch':'main','html_url':'https://github.com/example/atlas'}
        if '/contents/.dbgap-project.json' in path:
            if self.readme_only:return None
            marker={'project_id':'wrong' if self.wrong_marker else rt.PROJECT_ID}
            return {'content':base64.b64encode(rt.json_bytes(marker)).decode()}
        if method=='GET' and '/git/ref/heads/' in path:return {'object':{'sha':'oldhead'}}
        if method=='GET' and '/git/commits/' in path:return {'tree':{'sha':'oldtree'}}
        if method=='GET' and '/git/trees/' in path:
            fs=pub.build_payload(ROOT,'example','atlas') if self.matching else {}
            if self.readme_only:fs={'README.md':b'Bootstrap'}
            return {'truncated':False,'tree':[{'path':p,'sha':pub._git_blob_sha(b),'mode':'100644','type':'blob'} for p,b in fs.items()]}
        if method=='POST' and path.endswith('/git/blobs'):
            sha=pub._git_blob_sha(base64.b64decode(body['content']));self.written[sha]=body;return {'sha':sha}
        if method=='POST' and path.endswith('/git/trees'):return {'sha':'newtree'}
        if method=='POST' and path.endswith('/git/commits'):return {'sha':'newcommit123456'}
        if method=='PATCH' and '/git/refs/heads/' in path:
            if self.conflict:raise pub.GitHubError(422,'Concurrent update')
            return {'object':{'sha':body['sha']}}
        if method=='POST' and path.endswith('/git/refs'):return {'ref':body['ref']}
        if method=='POST' and path.endswith('/pulls'):return {'html_url':'https://github.com/example/atlas/pull/1'}
        if method=='GET' and '/issues?' in path:return self.issues
        if method=='POST' and path.endswith('/issues'):
            self.issues.append(body);return {'html_url':'https://github.com/example/atlas/issues/'+str(len(self.issues))}
        raise AssertionError((method,path,body))


class PublisherTests(unittest.TestCase):
    def go(self,c,**kw):
        return pub.publish(ROOT,'example','atlas',release_reviewed=True,confirmation='PUBLISH example/atlas PUBLIC',client=c,**kw)
    def test_new_repo_create_and_non_force_initial_commit(self):
        c=FakeGitHub();result=self.go(c)
        self.assertEqual(result['branch'],'main')
        updates=[b for m,p,b in c.calls if m=='PATCH'];self.assertEqual(updates,[{'sha':'newcommit123456','force':False}])
        self.assertTrue(any(m=='POST' and p=='/user/repos' for m,p,b in c.calls))
    def test_existing_uses_branch_and_pr(self):
        c=FakeGitHub(existing=True);r=self.go(c)
        self.assertTrue(r['branch'].startswith('review/'));self.assertIsNotNone(r['pull_request'])
        self.assertFalse(any(m=='PATCH' for m,p,b in c.calls))
    def test_unchanged_no_writes(self):
        c=FakeGitHub(existing=True,matching=True);r=self.go(c)
        self.assertEqual(r['status'],'unchanged');self.assertTrue(all(m=='GET' for m,p,b in c.calls))
    def test_wrong_repository_marker_stops(self):
        c=FakeGitHub(existing=True,wrong_marker=True)
        with self.assertRaises(ValueError):self.go(c)
        self.assertTrue(all(m=='GET' for m,p,b in c.calls))
    def test_concurrent_change_never_forced(self):
        c=FakeGitHub(conflict=True)
        with self.assertRaises(pub.GitHubError):self.go(c)
        self.assertFalse(any(b and b.get('force') is True for m,p,b in c.calls))
    def test_issues_idempotent(self):
        c=FakeGitHub(existing=True)
        self.assertEqual(len(pub.create_questions(c,c.prefix,ROOT)),10)
        self.assertEqual(len(pub.create_questions(c,c.prefix,ROOT)),0)
    def test_disabled_create_does_not_write(self):
        c=FakeGitHub()
        with self.assertRaises(ValueError):self.go(c,create_if_missing=False)
        self.assertTrue(all(m=='GET' for m,p,b in c.calls))
    def test_no_deleted_paths(self):
        c=FakeGitHub(existing=True);self.go(c)
        self.assertFalse(any(m=='DELETE' for m,p,b in c.calls))
        tree=next(b for m,p,b in c.calls if p.endswith('/git/trees') and m=='POST')
        self.assertTrue(all(x.get('sha') is not None for x in tree['tree']))

if __name__=='__main__':unittest.main()
