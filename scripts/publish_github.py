"""Preview or publish an explicit, code-only bundle using GitHub's REST API.

No force pushes, repository deletion, visibility changes, or Drive directory scans.
Existing populated repositories receive a review branch, not a main-branch update.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import getpass
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

from repo_tools import PROJECT_ID, json_bytes, read_public_files, sanitize_notebook, sha256, validate_payload

API_VERSION = '2026-03-10'
DESCRIPTION = 'Reproducible public-metadata analysis of dbGaP access, publications, clinical references, semantics and repository relationships.'


def validate_target(owner: str, repo: str, visibility: str) -> None:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner):
        raise ValueError('Enter a GitHub user or organization login, not a URL.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', repo) or repo.endswith('.git'):
        raise ValueError('Enter a repository name without slashes or .git.')
    if visibility not in {'public', 'private'}:
        raise ValueError('Visibility must be public or private.')


def confirmation_phrase(owner: str, repo: str, visibility: str) -> str:
    return f'PUBLISH {owner}/{repo} {visibility.upper()}'


def build_payload(root: Path, owner: str, repo: str, branch: str = 'main', notebook_updates=None) -> dict[str, bytes]:
    files = read_public_files(root)
    notebook_updates = notebook_updates or {}
    permitted_updates = {f'notebooks/0{i}_{n}.ipynb' for i, n in [(1,'collect'), (2,'analyze'), (3,'slides')]}
    for dest, src in notebook_updates.items():
        if dest not in permitted_updates:
            raise ValueError('Notebook override is not a canonical destination: ' + dest)
        p = Path(src)
        if p.is_symlink() or p.suffix != '.ipynb':
            raise ValueError('Override must be an explicit ordinary .ipynb file.')
        files[dest] = p.read_bytes()
    for name, data in list(files.items()):
        if name.endswith('.ipynb'):
            files[name] = sanitize_notebook(data)
        # Substitute only documentation fields, never analysis code.
        if name.endswith('.md') or name in {'CITATION.cff', 'docs/index.html'}:
            text = files[name].decode()
            files[name] = (text.replace('__OWNER__', owner).replace('__REPO__', repo)
                          .replace('__BRANCH__', branch)).encode()
    lineage = json.loads(files['provenance/source_notebooks.json'])
    for item in lineage['files']:
        name = item['repository_path']
        item.setdefault('adopted_code_cell_sha256',item['code_cell_sha256'].copy())
        item['prepared_file_sha256'] = sha256(files[name])
        if name in notebook_updates:
            nb = json.loads(files[name])
            item['code_cells_unchanged'] = False
            item['publisher_note'] = 'Explicit local notebook update supplied by maintainer; not a new scientific validation.'
            item['updated_input_sha256'] = sha256(Path(notebook_updates[name]).read_bytes())
            item['code_cell_sha256'] = [sha256(''.join(c['source']).encode()) for c in nb['cells'] if c['cell_type']=='code']
            item['code_cells'] = len(item['code_cell_sha256'])
    files['provenance/source_notebooks.json'] = json_bytes(lineage)
    # Do not call a sanitizer identical to the original notebook bytes: code identity is separate.
    record = {'schema_version':1, 'project_id':PROJECT_ID,
              'note':'Exact prepared code/documentation payload; not a scientific data release. Excludes itself.',
              'files':{n:{'sha256':sha256(b),'bytes':len(b)} for n,b in sorted(files.items()) if n!='provenance/package_manifest.json'}}
    files['provenance/package_manifest.json'] = json_bytes(record)
    errors = validate_payload(files)
    if errors:
        raise ValueError('\n'.join(errors))
    return files


def payload_fingerprint(files):
    return sha256(json_bytes({p:sha256(b) for p,b in sorted(files.items())}))


def preview(root: Path, owner: str, repo: str, visibility='public', notebook_updates=None):
    validate_target(owner, repo, visibility)
    files = build_payload(root, owner, repo, notebook_updates=notebook_updates)
    report = {'target':f'{owner}/{repo}', 'visibility':visibility, 'files':len(files),
              'bytes':sum(map(len,files.values())), 'payload_sha256':payload_fingerprint(files),
              'network_calls':0, 'excluded':'Scientific records, caches, execution outputs, and generated reports are not in the file allowlist.'}
    print(json.dumps(report,indent=2))
    for p,b in sorted(files.items()):
        print(f'  {len(b):>9,} bytes  {p}')
    print('\nPreview only. No GitHub credentials needed and nothing has been published.')
    return report, files


class GitHubError(RuntimeError):
    def __init__(self, status, message):
        self.status=status
        super().__init__(f'GitHub HTTP {status}: {message}')


class GitHubClient:
    def __init__(self, token: str):
        import requests
        self.session = requests.Session()
        self.session.headers.update({'Authorization':f'Bearer {token}',
                                     'Accept':'application/vnd.github+json',
                                     'X-GitHub-Api-Version':API_VERSION,
                                     'User-Agent':'dbgap-metadata-atlas-publisher/0.1'})
        self.last_write=0.0

    def request(self, method, path, body=None, allow_missing=False):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Only relative GitHub API paths are allowed.')
        if method not in {'GET','POST','PUT','PATCH'}:
            raise ValueError('Unsupported operation; no DELETE endpoint is used.')
        if method!='GET':
            time.sleep(max(0,1.05-(time.monotonic()-self.last_write)))
            self.last_write=time.monotonic()
        try:
            r=self.session.request(method,'https://api.github.com'+path,json=body,
                                   timeout=(10,60),allow_redirects=False)
        except Exception as e:
            raise RuntimeError('GitHub request did not complete; credentials/response bodies withheld. Rerun preview to inspect state.') from None
        if allow_missing and r.status_code==404:
            return None
        if not 200<=r.status_code<300:
            # Never include request headers, response body, token or raw prepared URL.
            detail={401:'Authentication failed.',403:'Permission, organization policy or rate limit blocked this operation.',
                    404:'Not found or inaccessible to this token.',409:'Repository state conflict.',
                    422:'Validation/conflict: inspect the target repository before retrying.',
                    429:'Rate limited; retry later, not in a tight loop.'}.get(r.status_code,'Operation failed.')
            permissions=r.headers.get('X-Accepted-GitHub-Permissions','')
            if permissions:detail+=' Accepted permissions: '+permissions[:200]
            raise GitHubError(r.status_code,detail)
        return r.json() if r.content else {}

    def close(self):
        self.session.headers.pop('Authorization',None)
        self.session.close()


def _git_blob_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()


def _repo_state(client, prefix, branch):
    ref=client.request('GET',prefix+'/git/ref/heads/'+quote(branch,safe='/'))
    head=ref['object']['sha']
    commit=client.request('GET',prefix+'/git/commits/'+head)
    tree=client.request('GET',prefix+'/git/trees/'+commit['tree']['sha']+'?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Remote tree was truncated. Refusing an incomplete comparison.')
    if any(x['type']!='tree' and x.get('mode') not in {'100644','100755'} for x in tree['tree']):
        raise ValueError('Remote repository contains symlinks or submodules; inspect manually.')
    return head, commit['tree']['sha'], {x['path']:x for x in tree['tree'] if x['type']=='blob'}


def publish(root, owner, repo, *, visibility='public', confirmation='', release_reviewed=False,
            create_if_missing=True, open_pull_request=True, enable_pages=False,
            seed_questions=False, notebook_updates=None, token=None, client=None):
    """Mutates GitHub only after explicit target-specific confirmation."""
    validate_target(owner,repo,visibility)
    if not release_reviewed or confirmation!=confirmation_phrase(owner,repo,visibility):
        raise ValueError('Publication requires release_reviewed=True and the exact target-specific confirmation phrase.')
    # Perform all local checks before authentication or any remote mutation.
    files=build_payload(Path(root),owner,repo,notebook_updates=notebook_updates)
    owned_client=client is None
    if owned_client:
        token=token or get_token()
        client=GitHubClient(token)
    try:
        user=client.request('GET','/user')
        prefix=f'/repos/{owner}/{repo}'
        info=client.request('GET',prefix,allow_missing=True)
        created=False
        if info is None:
            if not create_if_missing:
                raise ValueError('Repository missing/inaccessible; automatic creation is disabled.')
            endpoint='/user/repos' if owner.casefold()==user['login'].casefold() else f'/orgs/{owner}/repos'
            info=client.request('POST',endpoint,{'name':repo,'description':DESCRIPTION,
                    'private':visibility=='private','auto_init':True,'has_issues':True,'has_wiki':False})
            created=True
            print('Created repository:',info.get('html_url',f'https://github.com/{owner}/{repo}'))
        actual='private' if info.get('private') else 'public'
        if actual!=visibility:
            raise ValueError('Existing repository visibility differs. This tool never changes visibility.')
        if info.get('archived'):
            raise ValueError('Repository is archived.')
        branch=info.get('default_branch') or 'main'
        files=build_payload(Path(root),owner,repo,branch,notebook_updates)
        marker=client.request('GET',prefix+'/contents/.dbgap-project.json?ref='+quote(branch,safe=''),allow_missing=True)
        if marker:
            obj=json.loads(base64.b64decode(marker['content']))
            if obj.get('project_id')!=PROJECT_ID:
                raise ValueError('Target has a different project marker; refusing to overwrite it.')
        elif not created:
            # Permit only an empty or README/LICENSE-only starter repository.
            try:
                _,_,blobs=_repo_state(client,prefix,branch)
                if set(blobs)-{'README.md','LICENSE','NOTICE','.gitignore'}:
                    raise ValueError('Unmarked populated repository: refusing publication. Use a new dedicated repository.')
                if 'LICENSE' in blobs and 'LICENSE' not in files:
                    raise ValueError('Starter repository already has a LICENSE. Review it and include a consistent LICENSE/NOTICE and LICENSE_STATUS.md in the package before publishing.')
                created=True  # Explicitly confirmed empty/README-only starter.
            except GitHubError as e:
                if e.status not in {404,409}:raise
                client.request('PUT',prefix+'/contents/.dbgap-project.json',
                    {'message':'Initialize dbGaP Metadata Atlas repository identity',
                     'content':base64.b64encode(files['.dbgap-project.json']).decode()})
                info=client.request('GET',prefix);branch=info.get('default_branch') or 'main'
                created=True  # Empty-repository initialization: complete first commit on its default branch.
        head,tree_sha,remote=_repo_state(client,prefix,branch)
        changes={p:b for p,b in files.items() if remote.get(p,{}).get('sha')!=_git_blob_sha(b)}
        if not changes:
            print('No changed public code/documentation files. No commit created.')
            result={'repository':f'{owner}/{repo}','status':'unchanged','commit':head,'branch':branch}
        else:
            # Preserve remote files not explicitly named in our allowlist. Never delete by omission.
            paths=[]
            for p,b in sorted(changes.items()):
                obj=client.request('POST',prefix+'/git/blobs',{'content':base64.b64encode(b).decode(),'encoding':'base64'})
                paths.append({'path':p,'mode':'100644','type':'blob','sha':obj['sha']})
            tree=client.request('POST',prefix+'/git/trees',{'base_tree':tree_sha,'tree':paths})
            commit=client.request('POST',prefix+'/git/commits',{
                'message':'Publish reviewed dbGaP Metadata Atlas code and documentation',
                'tree':tree['sha'],'parents':[head]})
            if created:
                # force=False rejects a concurrent non-fast-forward update.
                client.request('PATCH',prefix+'/git/refs/heads/'+quote(branch,safe='/'),{'sha':commit['sha'],'force':False})
                target_branch=branch
                pr_url=None
            else:
                target_branch='review/dbgap-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+commit['sha'][:7]
                client.request('POST',prefix+'/git/refs',{'ref':'refs/heads/'+target_branch,'sha':commit['sha']})
                pr_url=None
                if open_pull_request:
                    try:
                        pr=client.request('POST',prefix+'/pulls',{'title':'Update dbGaP Metadata Atlas code and documentation',
                            'head':target_branch,'base':branch,
                            'body':'Code-only update. Inspect notebook source diffs, CI and publication policy before merging.\n\nPayload SHA-256: `'+payload_fingerprint(files)+'`.'})
                        pr_url=pr.get('html_url')
                    except GitHubError:
                        print('Review branch created; automatic PR opening failed. Use the repository compare page. No main-branch update was made.')
            result={'repository':f'{owner}/{repo}','status':'published','commit':commit['sha'],
                    'branch':target_branch,'pull_request':pr_url,'changed_files':len(changes),
                    'payload_sha256':payload_fingerprint(files)}
            print(json.dumps(result,indent=2))
        if seed_questions:
            try:
                result['issues']=create_questions(client,prefix,root)
            except GitHubError:
                result['issues_status']='Optional issue creation did not finish; code publication result is unchanged.'
                print(result['issues_status'])
        if enable_pages:
            if visibility!='public':
                raise ValueError('Pages is disabled for private targets by this publisher.')
            try:
                pages=client.request('GET',prefix+'/pages',allow_missing=True)
                if pages is None:
                    pages=client.request('POST',prefix+'/pages',{'build_type':'legacy','source':{'branch':branch,'path':'/docs'}})
                result['pages']=pages.get('html_url')
                print('Pages configured for documentation only; deployment is asynchronous and not verified here.')
            except GitHubError:
                print('Code publication succeeded; Pages configuration failed. Configure Settings > Pages > branch /docs manually.')
        return result
    finally:
        if owned_client:client.close()
        token=None


def create_questions(client,prefix,root):
    existing=set();page=1
    while True:
        rows=client.request('GET',prefix+f'/issues?state=all&per_page=100&page={page}')
        for row in rows:
            existing.update(re.findall(r'<!-- atlas-question:(Q\d\d) -->',row.get('body') or ''))
        if len(rows)<100:break
        page+=1
    out=[]
    for q in json.loads((Path(root)/'docs/research_questions.json').read_text()):
        if q['id'] in existing:continue
        body=f'<!-- atlas-question:{q["id"]} -->\n\n'+q['body']
        row=client.request('POST',prefix+'/issues',{'title':f'[{q["id"]}] {q["title"]}','body':body})
        existing.add(q['id']);out.append(row.get('html_url'))
    print(f'Created {len(out)} new question issues; existing markers were preserved.')
    return out


def get_token():
    # Do not hardcode, print, put in a URL, or save to git config.
    try:
        from google.colab import userdata
        token=userdata.get('GITHUB')
        if token and token.strip():return token.strip()
    except Exception:
        pass
    token=getpass.getpass('GitHub token (hidden; never paste into notebook source): ').strip()
    if not token:raise ValueError('No token supplied.')
    return token


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--owner',required=True);parser.add_argument('--repo',default=PROJECT_ID)
    parser.add_argument('--visibility',choices=['public','private'],default='public')
    parser.add_argument('--publish',action='store_true');parser.add_argument('--reviewed',action='store_true')
    args=parser.parse_args()
    preview(args.root,args.owner,args.repo,args.visibility)
    if args.publish:
        phrase=input('Type '+confirmation_phrase(args.owner,args.repo,args.visibility)+': ')
        publish(args.root,args.owner,args.repo,visibility=args.visibility,release_reviewed=args.reviewed,confirmation=phrase)
