#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Set, Tuple, Any


def check_npm_available() -> bool:
    npm = shutil.which('npm')
    node = shutil.which('node')
    return bool(npm and node)


def diag_npm_env() -> None:
    """Print diagnostic information about npm/node availability and PATH.

    This mirrors the functionality that used to live in a separate diagnostic
    script so users get a clear explanation when audits fail with "not_found".
    """

    print('\n=== npm/node diagnostic ===')
    print('shutil.which("npm") ->', shutil.which('npm'))
    print('shutil.which("node") ->', shutil.which('node'))

    try:
        p = subprocess.run(['npm', '--version'], capture_output=True, text=True, timeout=5)
        print("npm --version ->", p.returncode, p.stdout.strip())
    except FileNotFoundError as e:
        print('npm subprocess FileNotFoundError ->', repr(e))
    except Exception as e:
        print('npm subprocess error ->', repr(e))

    try:
        p = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
        print("node --version ->", p.returncode, p.stdout.strip())
    except FileNotFoundError as e:
        print('node subprocess FileNotFoundError ->', repr(e))
    except Exception as e:
        print('node subprocess error ->', repr(e))

    print('\nPATH (as seen by Python):')
    for p in os.environ.get('PATH', '').split(os.pathsep):
        print(p)
    print('=== end diagnostic ===\n')


def discover_project_dirs(start: str, exclude_venvs: bool = True) -> List[str]:
    """Recursively discover folders containing package.json or package-lock.json.

    When exclude_venvs is True, skip common Python virtualenv/site-packages
    locations (for example: .venv, venv, env, Lib/site-packages, share/jupyter)
    to avoid trying to run `npm` in those irrelevant folders.
    """
    
    print(f'Searching for npm projects under: {start}\n')
    found: Set[str] = set()
    for root, dirs, files in os.walk(start):
        # skip node_modules folders to avoid walking dependencies
        parts = [p.lower() for p in root.split(os.sep) if p]
        if 'node_modules' in parts:
            continue

        # Optionally skip typical Python virtualenv / site-packages locations
        if exclude_venvs:
            if any(p in ('.venv', 'venv', 'env') for p in parts):
                continue
            if 'site-packages' in parts:
                continue
            # skip shared jupyter extension folders under virtualenvs
            if 'share' in parts and 'jupyter' in parts:
                continue

        if 'package.json' in files or 'package-lock.json' in files:
            found.add(root)
            print(root)
    return sorted(found)


def load_check_targets(path: str) -> Set[str]:
    """Load a JSON file containing an array of targets.

    Expected format supported:
    - ["module@version", "other@1.2.3"]

    Returns a set of normalized strings: "module@version" with module lower-cased.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        raise SystemExit(f"Failed to load check file {path}: {e}")

    targets: Set[str] = set()
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, str):
                raise SystemExit(f"Invalid check file entry (must be strings like 'module@version'): {item!r}")
            if '@' in item:
                mod, ver = item.split('@', 1)
                targets.add(f"{mod.lower()}@{ver}")
    else:
        raise SystemExit(f"Check file must contain a JSON array of targets: {path}")

    return targets


def _read_package_version_from_path(pkg_path: str) -> Any:
    pj = os.path.join(pkg_path, 'package.json')
    if os.path.exists(pj):
        try:
            with open(pj, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('version')
        except Exception:
            return None
    return None


def _node_path_to_fs_path(node_path: str, project_root: str) -> str:
    if os.path.isabs(node_path):
        return node_path
    return os.path.normpath(os.path.join(project_root, node_path))


def _find_version_from_nodes(nodes: List[str], project_root: str) -> Any:
    # Try to resolve package versions by walking up from node paths
    for node in nodes:
        fs_path = _node_path_to_fs_path(node, project_root)
        cur = fs_path
        for _ in range(6):
            if os.path.isdir(cur):
                ver = _read_package_version_from_path(cur)
                if ver:
                    return ver
            parent = os.path.dirname(cur)
            if not parent or parent == cur:
                break
            cur = parent
    return None


def issue_matches_targets(issue: Dict, targets: Set[str], project_root: str) -> bool:
    """Return True if the issue corresponds to any target in `targets`.

    Matching logic (best-effort):
    - Check 'via' entries for module@version strings or dicts with 'version'
    - Check finding.version, finding.range, issue.range
    - Inspect 'nodes' and read nearby package.json versions
    """
    module = issue.get('module_name') or issue.get('id') or (issue.get('finding') or {}).get('name')
    if not module:
        return False
    module_l = module.lower()
    finding = issue.get('finding') or {}

    # 1) via entries
    via = finding.get('via') or []
    if isinstance(via, list):
        for v in via:
            if isinstance(v, str) and '@' in v:
                mod, ver = v.rsplit('@', 1)
                if mod.lower() == module_l and f"{module_l}@{ver}" in targets:
                    return True
            elif isinstance(v, dict):
                ver = v.get('version')
                modname = v.get('name') or module
                if ver and modname.lower() == module_l and f"{module_l}@{ver}" in targets:
                    return True

    # 2) direct version/range fields
    ver = finding.get('version')
    if ver and f"{module_l}@{ver}" in targets:
        return True

    rng = finding.get('range') or issue.get('range')
    if rng and f"{module_l}@{rng}" in targets:
        return True

    # 3) nodes -> filesystem lookup
    nodes = finding.get('nodes') or []
    if isinstance(nodes, list) and nodes:
        found = _find_version_from_nodes(nodes, project_root)
        if found and f"{module_l}@{found}" in targets:
            return True

    return False


def run_npm_audit(folder: str, timeout: int = 60) -> Dict:
    """Run `npm audit --json` in the given folder and return parsed JSON output or an error dict."""

    try:
        # Use subprocess to run npm audit
        proc = subprocess.run(run_npm_audit.cmdline, cwd=folder, capture_output=True, text=True, timeout=timeout, )
    except subprocess.TimeoutExpired:
        return {'error': 'timeout', 'folder': folder}
    except FileNotFoundError as e:
        return {'error': 'not_found', 'message': str(e), 'folder': folder}

    if proc.returncode not in (0, 1):
        # npm audit returns 1 when vulnerabilities are found; non-0/1 indicates issues
        return {'error': 'npm_failed', 'returncode': proc.returncode, 'stderr': proc.stderr}

    # Try to parse JSON
    try:
        data = json.loads(proc.stdout or '{}')
    except Exception:
        return {'error': 'invalid_json', 'stdout': proc.stdout, 'stderr': proc.stderr}

    return {'data': data, 'stdout': proc.stdout}


def extract_critical_issues(audit_data: Dict) -> List[Dict]:
    """Extract critical issues from npm audit JSON.

    The audit JSON schema has varied between npm versions; this helper checks
    multiple places where vulnerabilities/advisories may appear and extracts
    items labeled with severity 'critical'.

    Returns a list of issue dicts (preserving some original fields).
    """
    
    issues: List[Dict] = []
    # npm audit v6 schema places advisories in 'advisories' or 'vulnerabilities' depending on npm version
    if not audit_data:
        return issues
    
    # advisory style
    adv = audit_data.get('advisories') or {}
    for key, info in (adv.items() if isinstance(adv, dict) else []):
        severity = info.get('severity') or info.get('vuln', {}).get('severity')
        if severity == 'critical':
            issues.append({'id': key, 'title': info.get('title'), 'severity': severity, 'module_name': info.get('module_name'), 'url': info.get('url'), 'finding': info})

    # newer format: vulnerabilities map
    vulns = audit_data.get('vulnerabilities') or {}
    for name, info in (vulns.items() if isinstance(vulns, dict) else []):
        sev = info.get('severity')
        if sev == 'critical':
            # include paths and via info
            issues.append({'module_name': name, 'severity': sev, 'finding': info})

    # Also check 'metadata' summary
    metadata = audit_data.get('metadata') or {}
    if metadata.get('vulnerabilities', {}).get('critical'):
        # metadata contains counts; include as a high-level note
        issues.append({'metadata': metadata})

    return issues


def main(argv: List[str] | None = None) -> int:
    # Only accept a start path; all other settings are fixed to sensible defaults
    p = argparse.ArgumentParser(description='Run npm audit across discovered npm projects')
    p.add_argument('--start', '-s', help='Start folder to search (default current dir)', default='.')
    p.add_argument('--check-file', '-c', help='Path to JSON file containing module@version entries to explicitly check')
    args = p.parse_args(argv)

    start = os.path.abspath(args.start)
    if not os.path.isdir(start):
        print(f'Start folder does not exist: {start}', file=sys.stderr)
        return 2

    # Require npm and node to be available; otherwise print diagnostics and exit
    npm_path = shutil.which('npm')
    node_path = shutil.which('node')
    if not npm_path or not node_path:
        print("Error: 'npm' and/or 'node' not found on PATH. Aborting audits.", file=sys.stderr)
        diag_npm_env()
        return 3

    # Use the resolved npm executable
    run_npm_audit.cmdline = [npm_path, 'audit', '--json']
    # Load explicit check targets if provided
    check_targets: Set[str] | None = None
    if args.check_file:
        check_targets = load_check_targets(args.check_file)
        print(f'Loaded {len(check_targets)} explicit package@version targets from {args.check_file}')
    timeout = 60

    # Keep excluding common Python virtualenvs by default
    project_dirs = discover_project_dirs(start, exclude_venvs=True)
    print(f'\nFound {len(project_dirs)} project directories under {start}')

    report = {'start': start, 'projects_scanned': len(project_dirs), 'results': []}

    print()

    for proj in project_dirs:
        print('Auditing:', proj)
        res = run_npm_audit(proj)
        entry = {'folder': proj, 'error': None, 'critical_issues': [], 'raw': None}
        if 'error' in res:
            entry['error'] = res
        else:
            data = res.get('data') or {}
            entry['raw'] = data
            issues = extract_critical_issues(data)
            if check_targets:
                # Filter issues: only keep those that match the explicit targets
                filtered: List[Dict] = []
                for issue in issues:
                    if issue_matches_targets(issue, check_targets, proj):
                        filtered.append(issue)
                entry['critical_issues'] = filtered
            else:
                entry['critical_issues'] = issues
        report['results'].append(entry)

    # Tally critical counts
    total_critical = sum(len(e.get('critical_issues') or []) for e in report['results'])
    report['summary'] = {'total_projects': len(project_dirs), 'total_critical_issues': total_critical}

    # add a local timestamp for when the report was generated
    report['generated_at'] = datetime.now().astimezone().isoformat()

    # Build output filename from the start folder name and a local timestamp
    ts = datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z')
    start_name = os.path.basename(os.path.normpath(start)) or 'root'
    base_name = f"audits-{start_name}_{ts}"
    out_path = f"{base_name}.json"

    with open(out_path, 'w', encoding='utf-8') as out:
        json.dump(report, out, indent=2)

    print('\nWrote report to', out_path)

    # Create a module@version summary file adjacent to the audit report
    try:
        base, ext = os.path.splitext(out_path)
        summary_path = f"{base}_critical_versions{ext or '.json'}"
        summarize_critical_versions(report, summary_path)
        print('\nWrote module@version summary to', summary_path)
    except Exception as e:
        print('\nWarning: failed to write module@version summary:', e, file=sys.stderr)

    print()

    return 0

def summarize_critical_versions(report: Dict[str, Any], output_path: str, top_n: int | None = None) -> None:
    """Summarize module@version occurrences for critical findings.

    This function reads the `report` structure generated by the audit run and
    builds a counts map keyed by "module@version". It also gathers example
    locations for each module name. The result is written to `output_path` as
    JSON and a short, human-friendly list is printed to stdout.

    Parameters
    ----------
    report:
        The audit report dict as produced by this script.
    output_path:
        Path to write the JSON summary file.
    top_n:
        Optional limit for the printed/top array in the summary file. If None,
        all entries are included.
    """
    from collections import Counter, defaultdict

    def read_package_version(pkg_path: str) -> Any:
        """Return the package.json's version if present, else None."""
        pj = os.path.join(pkg_path, 'package.json')
        if os.path.exists(pj):
            try:
                with open(pj, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('version')
            except Exception:
                return None
        return None

    def node_path_to_fs_path(node_path: str, project_root: str) -> str:
        """Convert audit 'node' path to filesystem path (relative to project root).

        If the node_path is absolute, it is returned unchanged.
        """
        if os.path.isabs(node_path):
            return node_path
        return os.path.normpath(os.path.join(project_root, node_path))

    counts: Counter = Counter()
    examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for entry in report.get('results', []):
        proj = entry.get('folder')
        for issue in entry.get('critical_issues', []) or []:
            name = issue.get('module_name') or issue.get('id') or (issue.get('finding') or {}).get('name')
            if not name:
                continue

            finding = issue.get('finding') or {}
            nodes = finding.get('nodes') or []
            found_any = False
            for node in nodes:
                fs_path = node_path_to_fs_path(node, proj)
                cur = fs_path
                for _ in range(6):
                    if os.path.isdir(cur):
                        ver = read_package_version(cur)
                        if ver:
                            counts[f"{name}@{ver}"] += 1
                            examples[name].append({'version': ver, 'path': cur})
                            found_any = True
                            break
                    parent = os.path.dirname(cur)
                    if not parent or parent == cur:
                        break
                    cur = parent
                if found_any:
                    break

            if not found_any:
                rng = finding.get('range') or issue.get('range') or 'unknown'
                counts[f"{name}@{rng}"] += 1
                examples[name].append({'version': rng, 'path': None})

    summary: Dict[str, Any] = {
        'distinct_module_versions': len(counts),
        'total_occurrences': sum(counts.values()),
        'top': []
    }

    # Build items and sort by module name ascending (case-insensitive), then version
    items: List[Tuple[str, str, int]] = []
    for k, v in counts.items():
        module, ver = k.split('@', 1)
        items.append((module, ver, v))

    sorted_items = sorted(items, key=lambda x: (x[0].lower(), x[1]))
    selected = sorted_items if top_n is None else sorted_items[:top_n]
    for module, ver, v in selected:
        summary['top'].append({'module': module, 'version': ver, 'count': v})

    out = {'summary': summary, 'counts': dict(counts), 'examples': examples}
    out['generated_at'] = datetime.now().astimezone().isoformat()

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)

    # Print a short listing for convenience
    print('\nModule@version summary:')
    print(f"Distinct module@versions : {summary['distinct_module_versions']}")
    print(f"Total occurrences        : {summary['total_occurrences']}\n")
    for t in summary['top']:
        print(f"- {t['module']}@{t['version']}: {t['count']}")


if __name__ == '__main__':
    raise SystemExit(main())
