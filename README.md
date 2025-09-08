# Audit NPM Packages

Small, local Python tool to discover Node projects and run `npm audit --json` in each.

The script is intended for quick, offline sweeps of a filesystem tree (for example,
your development folder) to find projects and collect any critical vulnerabilities
reported by npm. It was created to help triage incidents involving compromised
packages and to produce reproducible JSON reports for further analysis.

Requirements
------------
- Python 3.8+
- Node.js and npm installed and available on PATH (the script checks this at startup)

Quick start
-----------
Audit a folder (recursively) and produce JSON outputs:

```shell
python .\run_npm_audits.py --start C:\Dev
```

```shell
python .\run_npm_audits.py -s C:\Dev
```

What the script does
--------------------
- Recursively finds folders that contain `package.json` or `package-lock.json`.
- Runs `npm audit --json` inside each discovered project.
- Produces two JSON files in the current directory:
  - `audits-<start>_<timestamp>.json` — the full audit report (projects and raw audit JSON)
  - `audits-<start>_<timestamp>_critical_versions.json` — a summarized map of module@version occurrences for critical findings

Notes on errors you may see
---------------------------
- If `npm` or `node` are not available on PATH the script will abort early and print a short diagnostic showing `shutil.which()` results, `npm --version` / `node --version` if available, and the PATH entries seen by Python. This prevents noisy per-folder "not_found" errors.

- On Windows, npm may be installed as `npm.cmd`; the script resolves the actual executable on PATH and uses that resolved path for subprocess calls.

Customization
-------------
- The script intentionally exposes only a single CLI parameter (`--start`) to keep usage simple. If you want an `--output` or `--npm-path` option, I can add them back in.

Troubleshooting
---------------
- If the script aborts because npm/node are missing, either install Node.js (https://nodejs.org/) or add the Node installation folder to your PATH. If you paste the diagnostic output here I can suggest the exact PATH change for Windows.

License / Notes
---------------
This is a small utility intended for local, offline analysis and triage. Use at your own risk; audit results depend on the version of `npm` installed.

Author
------
Simon Kurtz
GitHub: simonkurtz-MSFT
