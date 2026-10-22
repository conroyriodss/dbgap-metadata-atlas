"""Small, standard-library-only publication safeguards. No scientific computation."""
from __future__ import annotations
import ast
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

PROJECT_ID = 'dbgap-metadata-atlas'
ROOT_FILES = {'README.md', 'CITATION.cff', 'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md',
              'LICENSE_STATUS.md', 'LICENSE', 'NOTICE', '.gitignore', '.gitattributes',
              'requirements.txt', 'requirements-dev.txt', 'public_files.json', '.dbgap-project.json'}
TEXT_EXTENSIONS = {'.py', '.ipynb', '.md', '.json', '.yml', '.yaml', '.cff', '.txt', '.html', '.bib'}
BLOCKED_PARTS = {'.git', '.ipynb_checkpoints', '__pycache__', 'node_modules', 'data', 'outputs',
                 'raw', 'public_evidence', 'raw_public_evidence', 'semantic_sources', 'source_rows',
                 'private', 'credentials', 'secrets', 'work', '.venv'}
# Match actual credential-looking values, not variable names or placeholders.
SECRET_PATTERNS = [re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),
                   re.compile(r'github_pat_[A-Za-z0-9_]{40,}'),
                   re.compile(r'AKIA[0-9A-Z]{16}'),
                   re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
                   re.compile(r'https?://[^\s/@:]+:[^\s/@]+@github\.com', re.I)]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()


def allowed_path(name: str) -> bool:
    p = PurePosixPath(name)
    if not name or '\\' in name or p.is_absolute() or any(x in {'', '.', '..'} for x in name.split('/')):
        return False
    if any(x in BLOCKED_PARTS for x in p.parts):
        return False
    if len(p.parts) == 1:
        return name in ROOT_FILES
    if p.parts[0] not in {'notebooks', 'scripts', 'tests', 'docs', 'provenance', '.github'}:
        return False
    if name == 'docs/.nojekyll':
        return True
    if p.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    if p.suffix == '.html' and name != 'docs/index.html':
        return False  # No generated decks, dossiers, or explorers in this code-only publisher.
    return True


def notebook_codes(data: bytes) -> list[str]:
    return [''.join(c.get('source', [])) for c in json.loads(data)['cells'] if c.get('cell_type') == 'code']


def sanitize_notebook(data: bytes) -> bytes:
    nb = json.loads(data)
    if nb.get('nbformat') != 4:
        raise ValueError('Only nbformat 4 notebooks are supported.')
    nb['metadata'] = {k: v for k, v in nb.get('metadata', {}).items() if k in {'kernelspec', 'language_info'}}
    for i, cell in enumerate(nb.get('cells', [])):
        cell['metadata'] = {}
        cell.pop('attachments', None)
        cell['id'] = f'cell-{i:03d}'
        if cell.get('cell_type') == 'code':
            cell['outputs'] = []
            cell['execution_count'] = None
    cleaned = json_bytes(nb)
    if notebook_codes(data) != notebook_codes(cleaned):
        raise AssertionError('Sanitization changed scientific code.')
    return cleaned


def literal_secret_present(source: str) -> bool:
    """Catch obvious hardcoded credential assignments, without displaying their values."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        text = value.value.strip()
        if len(text) < 16 or any(word in text.upper() for word in ['YOUR_', 'PLACEHOLDER', 'EXAMPLE', 'REDACTED']):
            continue
        if any(isinstance(t, ast.Name) and re.search(r'(?:TOKEN|PASSWORD|SECRET|API_KEY)$', t.id, re.I) for t in targets):
            return True
    return False


def scan_bytes(name: str, data: bytes, strict_notebooks: bool = True) -> list[str]:
    errors = []
    if not allowed_path(name):
        errors.append('Path is outside the public code/documentation policy: ' + name)
    if len(data) > 5 * 1024 * 1024:
        errors.append('File exceeds the code-only 5 MiB limit: ' + name)
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return errors + ['Not UTF-8 text: ' + name]
    if any(p.search(text) for p in SECRET_PATTERNS):
        errors.append('Possible credential detected; value not printed: ' + name)
    if name.endswith('.ipynb'):
        try:
            nb = json.loads(text)
            for i, c in enumerate(nb['cells']):
                if c.get('cell_type') == 'code':
                    # Compilation only: NEVER run acquisition as part of a publication check.
                    ast.parse(''.join(c.get('source', [])), filename=f'{name}:cell-{i}')
                    if literal_secret_present(''.join(c.get('source', []))):
                        errors.append(f'Possible literal credential assignment at cell {i}: {name}')
                    if strict_notebooks and (c.get('outputs') or c.get('execution_count') is not None):
                        errors.append(f'Executed notebook cell {i}: {name}')
                if strict_notebooks and (c.get('attachments') or c.get('metadata')):
                    errors.append(f'Cell attachment/runtime metadata at cell {i}: {name}')
        except (ValueError, KeyError, SyntaxError, TypeError) as e:
            errors.append(f'Invalid notebook/code in {name}: {type(e).__name__}')
    elif name.endswith('.py'):
        try:
            ast.parse(text, filename=name)
            if literal_secret_present(text):
                errors.append('Possible literal credential assignment: ' + name)
        except SyntaxError as e:
            errors.append(f'Syntax error in {name} at line {e.lineno}')
    return errors


def read_public_files(root: Path) -> dict[str, bytes]:
    root = root.resolve()
    cfg = json.loads((root / 'public_files.json').read_text())
    paths = cfg['files']
    if len(paths) != len(set(paths)):
        raise ValueError('Duplicate public file paths.')
    result = {}
    for name in paths:
        if not allowed_path(name):
            raise ValueError('Blocked publication path: ' + name)
        p = root / name
        if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root):
            raise ValueError('Missing, unsafe, or symlinked public file: ' + name)
        result[name] = p.read_bytes()
    return result


def validate_payload(files: dict[str, bytes]) -> list[str]:
    errors = []
    for name, data in sorted(files.items()):
        errors.extend(scan_bytes(name, data))
    marker = json.loads(files.get('.dbgap-project.json', b'{}'))
    if marker.get('project_id') != PROJECT_ID:
        errors.append('Missing/wrong project identity marker.')
    return errors


def write_package_manifests(root: Path) -> dict:
    """Explicit maintenance operation. Admits source/docs only, never runtime data."""
    root = root.resolve()
    paths = []
    for p in sorted(root.rglob('*')):
        if not p.is_file():
            continue
        name = p.relative_to(root).as_posix()
        if allowed_path(name):
            if p.is_symlink():
                raise ValueError('Refusing symlink: ' + name)
            if name != 'provenance/package_manifest.json':
                paths.append(name)
    for name in ['public_files.json', 'provenance/package_manifest.json']:
        if name not in paths:
            paths.append(name)
    paths = sorted(paths)
    (root / 'public_files.json').write_bytes(json_bytes({'schema_version': 1, 'policy': 'code_and_docs_only', 'files': paths}))
    manifest = {'schema_version': 1, 'project_id': PROJECT_ID,
                'note': 'Hashes of this code package, not an empirical data snapshot. This manifest excludes itself.',
                'files': {n: {'sha256': sha256((root/n).read_bytes()), 'bytes': (root/n).stat().st_size}
                          for n in paths if n != 'provenance/package_manifest.json'}}
    (root / 'provenance/package_manifest.json').write_bytes(json_bytes(manifest))
    return manifest


def verify_package(root: Path) -> dict:
    data = read_public_files(root)
    errors = validate_payload(data)
    manifest = json.loads(data['provenance/package_manifest.json'])
    expected = set(data) - {'provenance/package_manifest.json'}
    if set(manifest['files']) != expected:
        errors.append('Package manifest and explicit file list differ.')
    for name, item in manifest['files'].items():
        if name not in data or sha256(data[name]) != item['sha256'] or len(data[name]) != item['bytes']:
            errors.append('Package file differs from manifest: ' + name)
    if errors:
        raise ValueError('\n'.join(errors))
    return {'files': len(data), 'bytes': sum(map(len, data.values())), 'scan': 'pass',
            'note': 'Pattern checks are not a complete privacy, security, copyright, or scientific review.'}


def extract_bundle(archive: Path, destination: Path) -> Path:
    """Validate ZIP member paths and sizes before extraction; do not execute contents."""
    if destination.exists():
        raise FileExistsError('Choose a new staging directory: ' + str(destination))
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > 400 or sum(i.file_size for i in infos) > 30 * 1024 * 1024:
            raise ValueError('Unexpectedly large code package.')
        seen = set()
        for i in infos:
            p = PurePosixPath(i.filename)
            if p.is_absolute() or '\\' in i.filename or '..' in p.parts or i.filename in seen:
                raise ValueError('Unsafe/duplicate archive path.')
            seen.add(i.filename)
            if stat.S_ISLNK(i.external_attr >> 16):
                raise ValueError('Symlinks are not accepted.')
            if len(p.parts) < 2 or p.parts[0] != PROJECT_ID:
                raise ValueError('Expected one dbgap-metadata-atlas package directory.')
            if not i.is_dir() and not allowed_path('/'.join(p.parts[1:])):
                raise ValueError('Unexpected archive member: ' + i.filename)
        destination.mkdir(parents=True)
        z.extractall(destination)
    root = destination / PROJECT_ID
    verify_package(root)
    return root
