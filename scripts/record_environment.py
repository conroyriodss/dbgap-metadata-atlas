"""Record actual package versions without credentials or raw data. No API calls."""
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
import platform
from pathlib import Path
import subprocess

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError('Refusing to overwrite an existing environment record.')
    root=Path(__file__).resolve().parents[1]
    def git(*args):
        r=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True)
        return r.stdout.strip() if r.returncode==0 else None
    record={'recorded_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
            'code_commit':git('rev-parse','HEAD'),'git_porcelain':git('status','--porcelain'),
            'packages':dict(sorted((x.metadata['Name'],x.version) for x in importlib.metadata.distributions() if x.metadata.get('Name'))),
            'note':'Runtime record only; not a scientific validation or dependency security audit. Review paths before publication.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(record,indent=2)+'\n')
    print('Environment recorded; review it separately before publication.')
