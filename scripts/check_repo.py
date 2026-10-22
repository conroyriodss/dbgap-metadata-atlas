"""Read-only checks for a public code repository; no acquisition or API requests."""
import argparse
from pathlib import Path
from repo_tools import verify_package, read_public_files, validate_payload


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--manifest',action='store_true')
    args=p.parse_args()
    if args.manifest:
        print(verify_package(args.root))
    else:
        files=read_public_files(args.root);errors=validate_payload(files)
        if errors:raise SystemExit('\n'.join(errors))
        print(f'PASS: {len(files)} declared public files; syntax, notebook hygiene and credential-pattern checks.')
        print('Not a scientific validation or authorization to redistribute upstream data.')
if __name__=='__main__':main()
