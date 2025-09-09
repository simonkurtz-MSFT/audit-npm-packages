# Audit NPM Packages

Small, local Python tool to discover Node projects and run `npm audit --json` in each.

The script is intended for quick, offline sweeps of a filesystem tree (for example,
your development folder) to find projects and collect any critical vulnerabilities
reported by npm. It was created to help triage incidents involving compromised
packages and to produce reproducible JSON reports for further analysis.

The [compromied npm packages on September 8, 2025](https://www.aikido.dev/blog/npm-debug-and-chalk-packages-compromised) motivated me to produce this.

**I deliberately wrote this in Python instead of using NodeJS.**

## Quick Usage

### Audit a folder (recursively) and produce JSON outputs:

```shell
python .\run_npm_audits.py -s C:\Dev
```

Wrap folders with whitespace in quotes:

```shell
python .\run_npm_audits.py -s "C:\Program Files"
```

### Audit a specific set of modules and versions

```shell
python .\run_npm_audits.py -s C:\Dev -c .\compromised_modules.json
```

## Requirements

- Python 3.8+
- Node.js and npm installed and available on PATH (the script checks this at startup)

## What the script does

- Recursively finds folders that contain `package.json` or `package-lock.json`.
- Runs `npm audit --json` inside each discovered project.
- Produces two JSON files in the current directory:
  - `audits-<start_directory>_<timestamp>.json` — the full audit report (projects and raw audit JSON)
  - `audits-<start_directory>_<timestamp>_critical_versions.json` — a summarized map of module@version occurrences for critical findings

## Usage

Run the script with an `-s` or `--start` parameter to supply a starting location.

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

Version matching
----------------
The check-file matching is exact by default:

- Module names are compared case-insensitively (they are normalized to lower-case).
- Versions are matched by exact string equality (for example `chalk@5.6.1` only matches the literal version `5.6.1`).
- Semver ranges (for example `chalk@^5.0.0`) are not supported today and will be treated as literal strings.

If you need semver/range support, please file an issue in this repo.

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
