# Audit NPM Packages

Small, local Python tool to discover Node projects and run `npm audit --json` in each.

The script is intended for quick, offline sweeps of a filesystem tree (for example,
your development folder) to find projects and collect any critical vulnerabilities
reported by npm. It was created to help triage incidents involving compromised
packages and to produce reproducible JSON reports for further analysis.

## Requirements

- Python 3.8+
- Node.js and npm installed and available on PATH (the script checks this at startup)

## What the script does

- Recursively finds folders that contain `package.json` or `package-lock.json`.
- Runs `npm audit --json` inside each discovered project.
- Produces two JSON files in the current directory:
  - `audits-<start>_<timestamp>.json` — the full audit report (projects and raw audit JSON)
  - `audits-<start>_<timestamp>_critical_versions.json` — a summarized map of module@version occurrences for critical findings

## Usage

Audit a folder (recursively) and produce JSON outputs:

```shell
python .\run_npm_audits.py --start C:\Dev
```

```shell
python .\run_npm_audits.py -s C:\Dev
```

### Check an explicit list of module@version pairs

If you want to only highlight specific module@version combinations (for
example, during an incident where certain packages/versions are known-compromised),
create a JSON file containing an array of targets. Supported entry formats:

Supported format:
- Simple strings: ["lodash@4.17.21", "chalk@2.4.2"]

Run the script with the `--check-file` (or `-c`) option:

```powershell
python .\run_npm_audits.py -s C:\Dev -c C:\path\to\targets.json
```

### Examples using the included `compromised_modules.json`

PowerShell (from the repo root):

```powershell
python .\run_npm_audits.py -s C:\Dev -c .\compromised_modules.json
```

POSIX / WSL:

```bash
python ./run_npm_audits.py -s /mnt/c/Dev -c ./compromised_modules.json
```

Sample expected output (shortened):

```
Found 4 project directories under C:\Dev
Auditing: C:\Dev\some\project
...
Wrote report to audits-Dev_20250908T135257-0400.json
Wrote module@version summary to audits-Dev_20250908T135257-0400_critical_versions.json
```

When `--check-file` is provided the generated report and printed summary will
only include matches for those module@version entries; other audit findings
are ignored.

## License / Notes

This is a small utility intended for local, offline analysis and triage. Use at your own risk; audit results depend on the version of `npm` installed.

## Author

Simon Kurtz
GitHub: simonkurtz-MSFT
