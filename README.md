[English](README.md) | [简体中文](README.zh-CN.md)

# Android App Analyzer

A Codex skill source package for downloading Android APK/XAPK files, extracting manifest metadata, and generating structured analysis reports for research, competitive analysis, and SDK inspection.

## Features

- Download the latest APK or XAPK from APKCombo by package name
- Use a managed cache workspace for repeated runs
- Extract the base APK from XAPK packages automatically
- Parse `AndroidManifest.xml` with `androguard`
- Detect permissions, background keep-alive strategies, push integrations, ad SDKs, and common third-party services
- Generate readable Markdown reports and run metadata for later review

## Why This Project

This project is designed for people who need a fast, scriptable way to inspect Android application packages without relying on the full Android SDK toolchain. It is especially useful for product research, growth analysis, monetization analysis, and lightweight security review.

## Requirements

- Python 3.8 or later
- `curl`
- Network access for dependency installation and package downloads

If `python` points to Python 2 on Windows, use `python3` or `py -3`.

## Installation

### Install as a Codex Skill (Recommended)

Install directly from GitHub with the skills CLI:

```bash
npx skills add MarkSunDev/skill-android-app-analyzer -g -y
```

This is the recommended installation path for end users.

### Install Python Dependencies Manually

Install dependencies manually:

```bash
python3 -m pip install -r requirements.txt
```

The scripts also support lazy dependency loading. Dependencies are only installed when a code path actually needs them. If automatic installation fails, the tool prints the exact manual install command.

## Managed Workspace

The analyzer always uses a managed cache workspace:

```text
.cache/
  android-app-analyzer/
    com.example.app/
      downloads/
      extracted/
      reports/
      temp/
      run.json
```

Rules:

- More than 5 package workspaces: warn and continue.
- More than 20 package workspaces: stop and require manual cleanup.

This version does not auto-delete old package folders. Cleanup stays explicit and user-controlled.

## Quick Start

Analyze an app by package name:

```bash
python3 android_analyzer.py com.kjvbibleadio.dailyverse
```

Analyze an existing local package:

```bash
python3 android_analyzer.py path/to/app.apk
```

Download only:

```bash
python3 apkcombo_download.py com.example.app
```

Use a custom workspace root:

```bash
python3 android_analyzer.py com.example.app --output D:\analysis-cache
```

Skip download and reuse a cached package in the managed workspace:

```bash
python3 android_analyzer.py com.example.app --skip-download
```

## Output Files

The analyzer can generate:

- `downloads/*.apk` or `downloads/*.xapk`
- `extracted/<xapk-name>/...`
- `reports/{package}_analysis.md`
- `reports/{apk_name}_manifest.xml`
- `run.json`

## APKCombo Download Notes

The downloader now follows APKCombo's current flow:

1. Open the resolved app page.
2. Find the download page.
3. Extract the internal `xid` value from page script content.
4. POST to `/<xid>/dl`.
5. Parse returned variant links.
6. Download the selected APK/XAPK with `curl`.

If APKCombo changes its HTML or internal endpoints again, `apkcombo_download.py` is the first place to update.

## Project Structure

- `SKILL.md`: Codex skill entry document
- `android_analyzer.py`: Main analysis workflow
- `apkcombo_download.py`: APK/XAPK downloader
- `workspace_manager.py`: Shared workspace management logic
- `dependency_bootstrap.py`: Shared dependency bootstrap logic
- `requirements.txt`: Python dependency list
- `tests/`: Unit tests for workspace, downloader parsing, and dependency bootstrap behavior
- `docs/plans/`: Design and implementation notes

## Install as a Codex Skill for Local Development

To use this project directly from your local Codex skill library, create a symbolic link:

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$HOME\\.codex\\skills\\android-app-analyzer" `
  -Target "C:\\path\\to\\this\\project"
```

## npm Package

This repository is distributed as a `skill-source` style npm package. The npm package ships the Codex skill files and Python implementation, but it is not the primary installation path for end users.

Use this repository with:

```bash
npx skills add MarkSunDev/skill-android-app-analyzer -g -y
```

Do not use unrelated commands such as `npx skill ...` for this project. That targets a different npm package and will fail.

## Testing

Run the unit tests with:

```bash
python3 -m unittest discover -s tests -v
```

## License

Released under the MIT License.
