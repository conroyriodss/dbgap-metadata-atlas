"""Drive inventory, reviewed notebook staging, and reversible cleanup for dbGaP.

No scientific API acquisition, source-data rewriting, deletion, trash, or permission changes.
Drive IDs are private operational provenance and are not placed in the GitHub payload.
"""
from __future__ import annotations
import ast
import copy
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

FOLDER = 'application/vnd.google-apps.folder'
SHORTCUT = 'application/vnd.google-apps.shortcut'
PROJECT = 'dbgap-metadata-atlas'
ARCHIVE_LABEL = '_dbgap_archive'
CONTROL_LABEL = '_dbgap_workspace_control'
MAX_NOTEBOOK_BYTES = 12 * 1024 * 1024
MAX_BINARY_CHECK_BYTES = 40 * 1024 * 1024
META = ('id,name,mimeType,parents,size,modifiedTime,createdTime,version,md5Checksum,'
        'sha256Checksum,trashed,driveId,webViewLink,shortcutDetails,'
        'capabilities(canDownload,canEdit,canAddChildren,canMoveItemWithinDrive)')
CANONICAL = {'A': 'notebooks/01_collect.ipynb', 'B': 'notebooks/02_analyze.ipynb',
             'C': 'notebooks/03_slides.ipynb'}
PREFERRED = {
    'A': ['dbGaP_A_Collection_Participation_Fixed.ipynb', '01_collect.ipynb'],
    'B': ['dbGaP_B_Participation_Replication_Analysis_Fixed.ipynb', '02_analyze.ipynb'],
    'C': ['dbGaP_C_Preliminary_14_Slides_Fixed.ipynb', '03_slides.ipynb'],
}
DATA_SUFFIXES = {'.parquet', '.csv', '.tsv', '.json', '.jsonl', '.ndjson', '.xml', '.gz',
                 '.owl', '.rdf', '.sqlite', '.db', '.feather', '.arrow', '.h5', '.hdf5'}
REPORT_SUFFIXES = {'.html', '.pptx', '.pdf', '.png', '.svg', '.md', '.txt', '.py', '.ipynb'}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def jbytes(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clean_name(name):
    # Only for grouping candidate names; never used as a filesystem path.
    name = re.sub(r'^(?:Copy of\s+)+', '', str(name), flags=re.I)
    return re.sub(r'\s*\(\d+\)(?=\.[^.]+$)', '', name).casefold()


def role_for(name):
    n = clean_name(name)
    for role, names in PREFERRED.items():
        if n in [x.casefold() for x in names]:
            return role
    m = re.match(r'dbgap_(?:notebook_)?([abc])(?:_|\b)', n)
    return m.group(1).upper() if m and n.endswith('.ipynb') else None


def notebook_summary(data):
    """Compile but NEVER execute notebook cells. Fingerprint ordered exact code sources."""
    obj = json.loads(data)
    if obj.get('nbformat') != 4 or not isinstance(obj.get('cells'), list):
        raise ValueError('Expected an nbformat 4 notebook.')
    code = []
    for i, cell in enumerate(obj['cells']):
        source = cell.get('source', [])
        source = source if isinstance(source, str) else ''.join(source)
        if cell.get('cell_type') == 'code':
            ast.parse(source, filename=f'notebook:cell-{i}')
            code.append(source)
    if not code:
        raise ValueError('Notebook has no code cells.')
    return {'raw_sha256': digest(data), 'code_sha256': digest(jbytes(code)),
            'code_cell_sha256': [digest(c.encode()) for c in code], 'code_cells': len(code),
            'has_outputs': any(c.get('outputs') or c.get('execution_count') is not None
                               for c in obj['cells'] if c.get('cell_type') == 'code')}


def snapshot(meta):
    return {k: meta.get(k) for k in ['id','name','mimeType','parents','version','modifiedTime',
                                    'size','md5Checksum','sha256Checksum','trashed','driveId']}


def snapshot_unchanged(old, current):
    return snapshot(old) == snapshot(current)


class GoogleDriveStore:
    """Small Google Drive v3 adapter. Uses bounded read retries; moves are not blindly retried."""
    def __init__(self, service):
        self.service = service
        self.reads = 0
        self.writes = 0

    def _execute(self, req, write=False):
        try:
            if write: self.writes += 1
            else: self.reads += 1
            return req.execute(num_retries=0 if write else 2)
        except Exception as exc:
            status = getattr(getattr(exc, 'resp', None), 'status', 'unknown')
            raise RuntimeError(f'Drive HTTP {status}: operation failed. Check account, folder access and permissions; no credentials or response body printed.') from None

    def meta(self, fid):
        return self._execute(self.service.files().get(fileId=fid, fields=META, supportsAllDrives=True))

    def children(self, fid):
        rows, token = [], None
        while True:
            kw = dict(q=f"'{fid}' in parents and trashed = false", pageSize=1000,
                      fields=f'nextPageToken,incompleteSearch,files({META})',
                      supportsAllDrives=True, includeItemsFromAllDrives=True)
            if token: kw['pageToken'] = token
            obj = self._execute(self.service.files().list(**kw))
            if obj.get('incompleteSearch'):
                raise ValueError('Drive returned incompleteSearch; no incomplete inventory will be used.')
            rows.extend(obj.get('files', []))
            token = obj.get('nextPageToken')
            if not token: return rows

    def bytes(self, fid, limit=MAX_NOTEBOOK_BYTES):
        m = self.meta(fid)
        if int(m.get('size') or 0) > limit:
            raise ValueError('File exceeds the configured small-file content limit: '+fid)
        if m.get('capabilities', {}).get('canDownload') is False:
            raise PermissionError('Drive does not permit downloading '+fid)
        if m['mimeType'].startswith('application/vnd.google-apps.'):
            raise ValueError('Native Workspace documents are not treated as notebook/binary files.')
        data = self._execute(self.service.files().get_media(fileId=fid, supportsAllDrives=True))
        if not isinstance(data, bytes) or len(data) > limit:
            raise ValueError('Unexpected or oversized downloaded content.')
        return data

    def create_folder(self, parent, name, kind):
        return self._execute(self.service.files().create(
            body={'name':name,'mimeType':FOLDER,'parents':[parent],
                  'appProperties':{'dbgap_workspace_kind':kind}}, fields=META, supportsAllDrives=True), True)

    def write_json(self, parent, name, obj, fid=None):
        from googleapiclient.http import MediaIoBaseUpload
        media = MediaIoBaseUpload(io.BytesIO(jbytes(obj)), mimetype='application/json', resumable=False)
        if fid:
            req = self.service.files().update(fileId=fid, media_body=media, fields=META, supportsAllDrives=True)
        else:
            req = self.service.files().create(body={'name':name,'parents':[parent]}, media_body=media,
                                              fields=META, supportsAllDrives=True)
        return self._execute(req, True)

    def move(self, fid, old_parent, new_parent):
        return self._execute(self.service.files().update(fileId=fid, addParents=new_parent,
            removeParents=old_parent, body={}, fields=META, supportsAllDrives=True), True)


def actual_folder(store, fid):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', str(fid)):
        raise ValueError('Use a Drive folder ID, not a path or URL.')
    m = store.meta(fid)
    if m.get('trashed'): raise ValueError('Requested folder is in trash.')
    if m['mimeType'] == SHORTCUT:
        target = m.get('shortcutDetails', {}).get('targetId')
        if not target: raise ValueError('Shortcut has no readable target.')
        m = store.meta(target)
    if m['mimeType'] != FOLDER or m.get('trashed'):
        raise ValueError('The supplied ID does not resolve to an active Drive folder.')
    return m


def mounted_path(store, folder, mount='/content/drive'):
    """Resolve a My Drive ancestry by ID and reject ambiguous sibling names.

    None is a legitimate result for Shared-with-me / Shared Drive / unusual mounts.
    All publishing and cleanup operations still work by ID in that case.
    """
    try:
        rootid = store.meta('root')['id']
        m, parts, seen = folder, [], set()
        while m['id'] != rootid:
            if m['id'] in seen or len(seen) > 100: return None
            seen.add(m['id'])
            if m.get('driveId') or len(m.get('parents', [])) != 1: return None
            name = m['name']
            if name in {'.','..'} or '/' in name or '\\' in name: return None
            parent = m['parents'][0]
            same = [c for c in store.children(parent) if c['name']==name]
            if len(same)!=1 or same[0]['id']!=m['id']: return None
            parts.append(name)
            m = store.meta(parent)
        p = Path(mount) / 'MyDrive'
        for part in reversed(parts): p /= part
        return str(p) if p.is_dir() else None
    except (RuntimeError, ValueError, KeyError, OSError):
        return None


def inventory(store, folder_ids, notebook_depth=2, max_items=12000, max_folders=100):
    """Metadata only. Data folder: direct children. Notebook folder: bounded traversal.

    No cache recursion, shortcuts followed, or collection-data downloads.
    """
    rows, seen_files, seen_folders = [], set(), set()
    for scope in ['data','notebooks']:
        fid = folder_ids[scope]
        queue = [(fid, '', 0)]
        while queue:
            parent, prefix, depth = queue.pop(0)
            key = (scope,parent)
            if key in seen_folders: continue
            seen_folders.add(key)
            if len(seen_folders)>max_folders:
                raise ValueError('Folder scan limit reached; narrow the notebook inventory depth.')
            for m in sorted(store.children(parent), key=lambda r:(r['name'].casefold(),r['id'])):
                if m.get('trashed'): continue
                rel = prefix + m['name']
                if m['id'] not in seen_files:
                    row = dict(m, workspace_scope=scope, relative_path=rel, source_parent=parent)
                    rows.append(row); seen_files.add(m['id'])
                # Only notebook subdirectories. Never traverse archives, data, caches, git or outputs.
                blocked = bool(re.search(r'(?:archive|cache|semantic_sources|public_evidence|outputs|\.git|preliminary\d|decks|source_rows)', m['name'], re.I))
                if scope=='notebooks' and m['mimeType']==FOLDER and depth<notebook_depth and not blocked:
                    queue.append((m['id'],rel+'/',depth+1))
                if len(rows)>max_items:
                    raise ValueError('Inventory item limit reached; no partial cleanup plan created.')
    return rows


def inspect_notebooks(store, rows, package_root, file_ids=None, cache=None, max_candidates=150):
    """Inspect project candidates only, with a bounded content-read budget.

    Unrelated notebook metadata stays in the inventory; its contents are not read.
    Explicit in-scope file IDs have priority, followed by complete sets of preferred
    A/B/C names, then historical project copies for cleanup. Never select a current
    version from a truncated set of competing candidates. Return deferred records
    for the private review report; cleanup keeps every uninspected notebook.
    """
    file_ids = file_ids or {}
    if set(file_ids) - set(CANONICAL):
        raise ValueError('NOTEBOOK_FILE_IDS accepts only roles A, B and C.')
    if (isinstance(max_candidates, bool) or not isinstance(max_candidates, int)
            or max_candidates < 3):
        raise ValueError('MAX_NOTEBOOK_INSPECTIONS must be an integer of at least 3.')
    requested = [v for v in file_ids.values() if v]
    if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', v) for v in requested):
        raise ValueError('Use individual notebook file IDs, not paths, URLs or folder IDs.')
    if len(requested) != len(set(requested)):
        raise ValueError('Each A/B/C role must use a different notebook file ID.')
    cache = cache if cache is not None else {}
    expected = {r:notebook_summary((Path(package_root)/p).read_bytes())['code_sha256']
                for r,p in CANONICAL.items()}
    listed = {r['id']:r for r in rows}
    explicit = set(requested)
    if explicit-set(listed):
        raise ValueError('A selected notebook ID is not in the scoped inventory: '+
                         ', '.join(sorted(explicit-set(listed))))
    def is_notebook(m):
        return (m.get('name', '').casefold().endswith('.ipynb')
                and m.get('mimeType') not in {FOLDER, SHORTCUT} and not m.get('trashed'))
    if any(not is_notebook(listed[fid]) for fid in explicit):
        raise ValueError('An explicit selection is not an active notebook file (folders/shortcuts are not supported).')
    possible = [m for m in rows if is_notebook(m)
                and (role_for(m['name']) or m['id'] in explicit)]
    possible.sort(key=lambda m:(m.get('workspace_scope')!='notebooks', m['name'].casefold(), m['id']))
    pools = {}
    for role in CANONICAL:
        if file_ids.get(role):
            pools[role] = [listed[file_ids[role]]]
        else:
            same_role = [m for m in possible if role_for(m['name'])==role and m['id'] not in explicit]
            preferred = [m for m in same_role if clean_name(m['name']) in
                         [n.casefold() for n in PREFERRED[role]]]
            pools[role] = preferred or same_role
    queue = [listed[fid] for fid in sorted(explicit)]
    queued = set(explicit)
    budget_blocked = set()
    for role, pool in pools.items():
        needed = [m for m in pool if m['id'] not in queued]
        if len(queue)+len(needed) > max_candidates:
            budget_blocked.add(role)
            continue
        queue.extend(needed)
        queued.update(m['id'] for m in needed)
    # Optional older versions are inspected only after all possible current roles.
    blocked_ids = {m['id'] for role in budget_blocked for m in pools[role]}
    for m in possible:
        if len(queue) >= max_candidates:
            break
        if m['id'] not in queued and m['id'] not in blocked_ids:
            queue.append(m)
            queued.add(m['id'])
    by_id = {}
    for m in queue:
        role = role_for(m['name'])
        if not role:
            role = next((r for r, fid in file_ids.items() if fid==m['id']), None)
        try:
            sig = json.dumps(snapshot(m), sort_keys=True)
            key = m['id']+'|'+sig
            if key not in cache:
                cache[key] = store.bytes(m['id'])
            data = cache[key]
            summary = notebook_summary(data)
            if not snapshot_unchanged(m, store.meta(m['id'])):
                raise ValueError('Notebook changed while inventorying; rerun preview.')
            by_id[m['id']] = dict(m, role=role, **summary, inspection_status='inspected',
                                  expected_code=summary['code_sha256']==expected.get(role))
        except (ValueError, SyntaxError, RuntimeError, PermissionError, OSError,
                KeyError, TypeError, AttributeError) as exc:
            by_id[m['id']] = dict(m, role=role, inspection_status='error',
                                  inspection_error=type(exc).__name__+': '+str(exc)[:160])
    for m in possible:
        if m['id'] not in by_id:
            by_id[m['id']] = dict(m, role=role_for(m['name']), inspection_status='deferred',
                inspection_deferred=True, inspection_error='Not inspected: project notebook budget reached; retained in place.')
    candidates = [by_id[m['id']] for m in possible]
    selected, errors = {}, []
    for role in CANONICAL:
        if role in budget_blocked:
            errors.append(f'{role}: {len(pools[role]):,} competing candidates exceed the inspection budget; '
                          'choose NOTEBOOK_FILE_IDS from notebook_candidates.csv. No partial choice made.')
            continue
        cand = [by_id[m['id']] for m in pools[role]]
        if file_ids.get(role):
            if not cand or cand[0].get('inspection_error'):
                errors.append(role+': explicit notebook cannot be inspected; see notebook_candidates.csv.')
                continue
        else:
            if any(m.get('inspection_error') for m in cand):
                errors.append(role+': intended notebook could not be inspected; inspect candidate errors.')
                continue
            preferred = [m for m in cand if clean_name(m['name']) in [n.casefold() for n in PREFERRED[role]]]
            cand = preferred or [m for m in cand if m.get('expected_code')]
            if not cand:
                errors.append(role+': no recognized current notebook; enter its file ID from drive_inventory.csv.')
                continue
            if len({m['code_sha256'] for m in cand}) != 1:
                errors.append(role+': multiple different code versions; choose NOTEBOOK_FILE_IDS explicitly.')
                continue
        def rank(m):
            return (m.get('workspace_scope')!='notebooks',
                    m['name'].casefold() not in [n.casefold() for n in PREFERRED[role]],
                    m['name'].casefold(), m['id'])
        chosen = sorted(cand, key=rank)[0]
        if chosen.get('role') and chosen['role'] != role:
            errors.append(role+': selected filename identifies a different notebook role.')
            continue
        selected[role] = chosen
    return selected, candidates, errors, cache


def inspection_stats(rows, candidates):
    notebooks = [m for m in rows if m.get('name', '').casefold().endswith('.ipynb')
                 and m.get('mimeType') not in {FOLDER, SHORTCUT}]
    return {'notebooks_listed': len(notebooks), 'project_candidates': len(candidates),
            'unrelated_notebooks_not_read': len(notebooks)-len(candidates),
            'inspected': sum(m.get('inspection_status')=='inspected' for m in candidates),
            'errors': sum(m.get('inspection_status')=='error' for m in candidates),
            'deferred': sum(m.get('inspection_status')=='deferred' for m in candidates)}


def inventory_request(data_folder_id, notebook_folder_id, file_ids, notebook_depth, max_candidates):
    """Bind ready state to the settings that produced it; publication toggles are excluded."""
    return json.dumps({'data_folder_id':data_folder_id, 'notebook_folder_id':notebook_folder_id,
                       'file_ids':file_ids, 'notebook_depth':notebook_depth,
                       'max_candidates':max_candidates}, sort_keys=True)


def cached_bytes(meta, cache):
    return cache[meta['id']+'|'+json.dumps(snapshot(meta),sort_keys=True)]


def stage_notebooks(package_root, staged_root, selected, cache, source_ids_public=False):
    if source_ids_public:
        raise ValueError('Drive IDs and folder paths do not belong in the public code payload.')
    import shutil
    from repo_tools import sanitize_notebook, write_package_manifests, verify_package
    staged=Path(staged_root)
    if staged.exists(): raise FileExistsError('Choose a new local staging directory.')
    if set(selected)!=set(CANONICAL):
        raise ValueError('All three A/B/C notebooks must be selected before staging.')
    shutil.copytree(package_root,staged)
    lineage_path=staged/'provenance/source_notebooks.json'
    lineage=json.loads(lineage_path.read_text())
    records=[]
    for role, dest in CANONICAL.items():
        meta=selected[role]; raw=cached_bytes(meta,cache)
        if digest(raw)!=meta['raw_sha256']:
            raise ValueError('Notebook byte fingerprint changed.')
        cleaned=sanitize_notebook(raw)
        if notebook_summary(cleaned)['code_sha256']!=meta['code_sha256']:
            raise AssertionError('Notebook cleaning changed code.')
        (staged/dest).write_bytes(cleaned)
        summary=notebook_summary(cleaned)
        for item in lineage['files']:
            if item['repository_path']==dest:
                item.setdefault('adopted_code_cell_sha256',item['code_cell_sha256'].copy())
                item.update(prepared_file_sha256=digest(cleaned),code_cell_sha256=summary['code_cell_sha256'],
                            code_cells=summary['code_cells'],
                            code_cells_unchanged=summary['code_cell_sha256']==item['adopted_code_cell_sha256'],
                            publisher_note='Source selected explicitly or by matching current names/code. No scientific execution in workspace manager.')
        records.append({'role':role,'repository_path':dest,
                        'prepared_sha256':digest(cleaned),'code_sha256':summary['code_sha256'],
                        'matches_adopted_scientific_code':meta.get('expected_code',False)})
    lineage_path.write_bytes(jbytes(lineage))
    (staged/'provenance/drive_selected_notebooks.json').write_bytes(jbytes({
        'scope':'Notebook bytes from a maintainer-selected Drive workspace; no folder IDs or paths published.',
        'notebooks':records}))
    write_package_manifests(staged)
    verify_package(staged)
    return staged


def cleanup_plan(rows, selected, candidates, active_names=()):
    """Conservative proposals only. No age-based data, cache, directory or checkpoint cleanup.

    Downloads with a numbered-copy suffix may be duplicate candidates if the exact unnumbered
    original is present. Current selected notebooks are always protected.
    """
    keep_ids={m['id'] for m in selected.values()}
    by_id={m['id']:m for m in candidates}
    names=set(active_names)
    result=[]
    for m in rows:
        item={'id':m['id'],'name':m['name'],'scope':m['workspace_scope'],
              'relative_path':m['relative_path'],'source_parent':m['source_parent'],
              'action':'KEEP','reason':'Unclassified: kept in place.','keeper_id':None,
              'snapshot':snapshot(m)}
        name=m['name']; low=name.casefold(); ext=Path(low).suffix
        c=by_id.get(m['id'],{})
        if m['id'] in keep_ids:
            item['reason']='Selected current A/B/C notebook.'
        elif m['mimeType'] in {FOLDER,SHORTCUT}:
            item['reason']='Folder/shortcut: never automatically moved.'
        elif ext in DATA_SUFFIXES or re.search(r'checkpoint|manifest|ledger|journal|refresh_state|run_report|config|credentials|secret|\.env',low):
            item['reason']='Protected data, checkpoint, provenance, configuration or secret file.'
        elif name in names:
            item['reason']='Literal file dependency in selected source: kept in place.'
        elif c.get('inspection_error'):
            item['reason']='Notebook inspection failed; retained for manual review.'
        elif c.get('role') in selected:
            current=selected[c['role']]
            # Only same-code copies are auto-suggested. Different versions need explicit review.
            if c.get('code_sha256')==current.get('code_sha256'):
                item.update(action='SUGGEST_ARCHIVE',reason='Same ordered code cells as selected notebook; original outputs/notes remain in archive.',keeper_id=current['id'])
            else:
                item.update(action='REVIEW_VERSION',reason='Different notebook code; not proven obsolete. Select its ID only after review.')
        elif ext in REPORT_SUFFIXES and re.search(r'(?:dbgap|mesh|reporter|publish_dbgap)', low):
            originals=[o for o in rows if o['id']!=m['id'] and o['source_parent']==m['source_parent']
                       and o['name'].casefold()==clean_name(name) and o['name']==re.sub(r'\s*\(\d+\)(?=\.[^.]+$)','',name)
                       and o['mimeType'] not in {FOLDER,SHORTCUT}]
            if clean_name(name)!=low and len(originals)==1 and m.get('md5Checksum') and m.get('md5Checksum')==originals[0].get('md5Checksum'):
                item.update(action='SUGGEST_ARCHIVE',reason='Numbered project copy matching an unnumbered original by Drive MD5; SHA-256 recheck required before move.',keeper_id=originals[0]['id'])
            elif ext in {'.ipynb','.py','.html','.pptx','.pdf','.png','.svg','.md','.txt'}:
                item.update(action='REVIEW_EXPORT',reason='Project code/report export: optional archive only by explicit file ID; may still be referenced.')
        result.append(item)
    return result


def literal_dependencies(selected,cache):
    names=set()
    for m in selected.values():
        nb=json.loads(cached_bytes(m,cache))
        for cell in nb['cells']:
            if cell['cell_type']!='code': continue
            source=cell.get('source',[]);source=source if isinstance(source,str) else ''.join(source)
            try: tree=ast.parse(source)
            except SyntaxError: continue
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,str) and '\n' not in node.value:
                    v=node.value
                    if len(v)<500 and Path(v).suffix.casefold() in DATA_SUFFIXES|REPORT_SUFFIXES:
                        names.add(Path(v).name)
    return names


def write_reports(local, rows, selected, candidates, errors, plan):
    local=Path(local);local.mkdir(parents=True,exist_ok=True)
    for filename,obj in [('drive_inventory.json',rows),('notebook_candidates.json',candidates),
                         ('notebook_selection.json',{'selected':selected,'errors':errors}),('cleanup_plan.json',plan)]:
        (local/filename).write_bytes(jbytes(obj))
    for filename,items,columns in [
        ('drive_inventory.csv',rows,['id','name','mimeType','workspace_scope','relative_path','size','modifiedTime','md5Checksum']),
        ('cleanup_plan.csv',plan,['id','name','scope','relative_path','action','reason','keeper_id']),
        ('notebook_candidates.csv',candidates,['id','name','role','workspace_scope','relative_path',
         'inspection_status','expected_code','code_cells','code_sha256','inspection_error'])]:
        with (local/filename).open('w',newline='',encoding='utf-8') as h:
            w=csv.DictWriter(h,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(items)
    return local


def show_inventory(rows,selected,candidates,errors,plan):
    print(f'Inventory: {len(rows):,} entries; metadata only except inspected notebooks.')
    print('Notebook inspection:', inspection_stats(rows, candidates))
    print('Classification:',dict(Counter(p['action'] for p in plan)))
    for role,m in selected.items():
        print(f"{role}: {m['name']} | ID {m['id']} | {m['code_cells']} code cells | adopted code match={m.get('expected_code')}")
        print('   Open in Colab: https://colab.research.google.com/drive/'+m['id'])
    if errors:
        print('\nSelection needs attention. Set NOTEBOOK_FILE_IDS using the following IDs:')
        for error in errors: print('  '+error)
        for c in candidates[:30]:
            print(' ',c.get('role'),c['name'],'ID='+c['id'],c.get('inspection_error','code='+c.get('code_sha256','')[:12]))
        if len(candidates)>30:
            print(f'  Showing 30 of {len(candidates):,} candidates; complete IDs/statuses in notebook_candidates.csv.')
    print('\nArchive suggestions (nothing moved):')
    for p in plan:
        if p['action']=='SUGGEST_ARCHIVE': print(' ',p['id'],p['name'],'--',p['reason'])
    print('Other versions/exports remain REVIEW only. Full inventories stay local, not in GitHub.')


def pick_archive_items(plan, ids=(), include_suggested=False):
    ids=set(ids)
    byid={p['id']:p for p in plan}
    if ids-set(byid): raise ValueError('An archive ID is not in this reviewed inventory.')
    if include_suggested: ids|={p['id'] for p in plan if p['action']=='SUGGEST_ARCHIVE'}
    out=[]
    for fid in sorted(ids):
        item=byid[fid]
        if item['action'] not in {'SUGGEST_ARCHIVE','REVIEW_VERSION','REVIEW_EXPORT'}:
            raise ValueError('Refusing to archive a protected/current file: '+item['name'])
        out.append(copy.deepcopy(item))
    return out


def archive_phrase(items):
    return f'ARCHIVE {len(items)} FILES '+digest(jbytes(items))[:12]


def _check_move_capability(store,meta):
    if meta.get('capabilities',{}).get('canMoveItemWithinDrive') is not True:
        raise PermissionError('Drive did not confirm move permission for '+meta['id'])
    if len(meta.get('parents',[]))!=1:
        raise ValueError('Refusing file with unexpected parent count.')
    parent=store.meta(meta['parents'][0])
    if parent.get('capabilities',{}).get('canAddChildren') is not True:
        raise PermissionError('Cannot create archive under the original parent.')
    return parent


def archive_files(store,items,confirmation,local_dir,selected_ids=()):
    """Two-phase journal before moves; no deletions. User must retain the journal ID.

    A new archive is placed below each ORIGINAL parent. Folder permissions are inherited;
    no existing archive is reused and no sharing permission is created or edited.
    """
    if not items: return {'status':'nothing_selected','moved':0}
    if confirmation!=archive_phrase(items): raise ValueError('Archive confirmation did not match the reviewed plan.')
    local=Path(local_dir);local.mkdir(parents=True,exist_ok=True)
    parents={}; evidence={}
    for item in items:
        if item['id'] in set(selected_ids): raise ValueError('Selected notebook is protected.')
        if item['action'] not in {'SUGGEST_ARCHIVE','REVIEW_VERSION','REVIEW_EXPORT'}:
            raise ValueError('Protected archive item.')
        now=store.meta(item['id'])
        if not snapshot_unchanged(item['snapshot'],now):
            raise ValueError('File changed since preview; rerun preview: '+item['name'])
        if now['mimeType'] in {FOLDER,SHORTCUT} or Path(now['name']).suffix.casefold() not in REPORT_SUFFIXES:
            raise ValueError('Cleanup never moves source data, folders or shortcuts.')
        if now.get('parents') != [item['source_parent']]:
            raise ValueError('Planned parent differs from actual parent.')
        parent=_check_move_capability(store,now);parents[parent['id']]=parent
        data=store.bytes(item['id'],limit=MAX_BINARY_CHECK_BYTES)
        evidence[item['id']]=digest(data)
        keeper=item.get('keeper_id')
        if keeper:
            if keeper in {i['id'] for i in items}: raise ValueError('A duplicate keeper is also scheduled for archive.')
            km=store.meta(keeper)
            other=store.bytes(keeper,limit=MAX_BINARY_CHECK_BYTES)
            if now['name'].lower().endswith('.ipynb'):
                if notebook_summary(data)['code_sha256']!=notebook_summary(other)['code_sha256']:
                    raise ValueError('Keeper code differs; redo inventory.')
            elif digest(data)!=digest(other):
                raise ValueError('Duplicate bytes differ; refusing move.')
        # Repeat after download to catch autosave while reading.
        if not snapshot_unchanged(now,store.meta(item['id'])):
            raise ValueError('File changed during archive preflight.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+digest(jbytes(items))[:8]
    archive_by_parent={}
    for pid in sorted(parents):
        m=store.create_folder(pid,ARCHIVE_LABEL+'_'+stamp,'archive')
        archive_by_parent[pid]=m['id']
    journal={'schema_version':1,'project_id':PROJECT,'kind':'reversible_drive_archive','created_utc':utc_now(),
             'entries':[dict(item,archive_parent=archive_by_parent[item['source_parent']],sha256=evidence[item['id']],status='pending') for item in items],
             'no_delete':True,'permissions_note':'Moved only below original parent; ACL inheritance is re-evaluated by Drive. Restore does not recreate historical sharing permissions.'}
    # Do not put a cross-folder inventory into a potentially broadly shared source folder.
    # A new My Drive folder is created with no added permissions; its URL is printed.
    journal_folder=store.create_folder('root',CONTROL_LABEL+'_'+stamp,'private_journal')
    first_parent=journal_folder['id']
    jm=store.write_json(first_parent,'archive_journal.json',journal);jid=jm['id']
    journal['journal_file_id']=jid
    local_journal=local/('archive_journal_'+stamp+'.json')
    def save():
        local_journal.write_bytes(jbytes(journal))
        store.write_json(first_parent,'archive_journal.json',journal,fid=jid)
    save()
    print('Recovery journal ID:',jid)
    print('Recovery journal link: https://drive.google.com/file/d/'+jid+'/view')
    try:
        for item in journal['entries']:
            current=store.meta(item['id'])
            if not snapshot_unchanged(item['snapshot'],current):
                item['status']='skipped_changed';save();continue
            item['status']='move_intent';save()  # persisted before the actual move
            try:
                store.move(item['id'],item['source_parent'],item['archive_parent'])
            except RuntimeError:
                # A network failure can happen after the server committed the move.
                current=store.meta(item['id'])
                if current.get('parents')!=[item['archive_parent']]:
                    item['status']='move_error';save();raise
            current=store.meta(item['id'])
            if current.get('parents')!=[item['archive_parent']]:
                item['status']='unexpected_parent';save();raise ValueError('Unexpected parent after move.')
            if digest(store.bytes(item['id'],limit=MAX_BINARY_CHECK_BYTES))!=item['sha256']:
                item['status']='moved_content_changed';save();raise ValueError('Content changed during move; inspect journal.')
            item['status']='archived';item['archived_utc']=utc_now();save()
    finally:
        local_journal.write_bytes(jbytes(journal))
    return {'status':'archived','moved':sum(e['status']=='archived' for e in journal['entries']),
            'journal_id':jid,'local_journal':str(local_journal),'archive_folders':archive_by_parent}


def restore_archive(store,journal_id,confirmation,allowed_root_ids):
    if confirmation!='RESTORE '+journal_id:
        raise ValueError('Restore needs the exact journal-specific phrase.')
    journal=json.loads(store.bytes(journal_id))
    if journal.get('project_id')!=PROJECT or journal.get('kind')!='reversible_drive_archive':
        raise ValueError('Not a dbGaP workspace archive journal.')
    def descends(fid):
        seen=set()
        while fid not in allowed_root_ids:
            if fid in seen or len(seen)>100: return False
            seen.add(fid);m=store.meta(fid)
            if len(m.get('parents',[]))!=1: return False
            fid=m['parents'][0]
        return True
    restored=0
    for item in journal['entries']:
        if not descends(item['source_parent']) or not descends(item['archive_parent']):
            raise ValueError('Journal path is outside the two configured workspace folders.')
        now=store.meta(item['id'])
        if now.get('parents')==[item['source_parent']]: continue
        if now.get('parents')!=[item['archive_parent']]:
            raise ValueError('File is no longer in its recorded archive; not moved.')
        if now.get('trashed') or now.get('mimeType') in {FOLDER,SHORTCUT}:
            raise ValueError('Archived item is trashed or changed type; inspect manually.')
        if digest(store.bytes(item['id'],limit=MAX_BINARY_CHECK_BYTES))!=item['sha256']:
            raise ValueError('Archived file content changed; inspect instead of automatic restore.')
        original=store.meta(item['source_parent'])
        if original.get('trashed') or original.get('capabilities',{}).get('canAddChildren') is not True:
            raise PermissionError('Original folder is unavailable or not writable.')
        conflict=[m for m in store.children(item['source_parent']) if m['name']==now['name'] and m['id']!=now['id']]
        if conflict: raise ValueError('Original folder now contains that filename; resolve before restoring.')
        if now.get('capabilities',{}).get('canMoveItemWithinDrive') is not True:
            raise PermissionError('Drive has not confirmed restore permission.')
        store.move(item['id'],item['archive_parent'],item['source_parent'])
        if store.meta(item['id']).get('parents')!=[item['source_parent']]:
            raise ValueError('Restore parent check failed.')
        item['status']='restored';item['restored_utc']=utc_now();restored+=1
        store.write_json(store.meta(journal_id)['parents'][0],'archive_journal.json',journal,fid=journal_id)
    return {'status':'restored','restored':restored,'journal_id':journal_id}


def selection_still_current(store,selected):
    for meta in selected.values():
        if not snapshot_unchanged(meta,store.meta(meta['id'])):
            raise ValueError('Selected source notebook changed since preview; rerun preview before publishing.')


def github_secret(name='GITHUB'):
    """Read only the requested Colab Secret. No environment fallback or echo."""
    try:
        from google.colab import userdata
        token=userdata.get(name)
    except Exception:
        raise ValueError('Grant this notebook access to the Colab secret named '+name+'. Do not paste its value into code.') from None
    if not isinstance(token,str) or not token.strip():
        raise ValueError('The configured Colab secret is empty.')
    token=token.strip()
    if 'PRIVATE KEY' in token or '\n' in token:
        raise ValueError('This REST publisher requires a GitHub access token, not an SSH private key.')
    return token
