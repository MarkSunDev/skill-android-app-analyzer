[English](README.md) | [简体中文](README.zh-CN.md)

# Android App Analyzer

A Codex skill source package for downloading Android APK/XAPK files, extracting manifest metadata, and generating structured analysis reports for research, competitive analysis, and SDK inspection.

## Features

- Download the latest APK or XAPK from apkcombo by package name
- Extract the base APK from XAPK packages automatically
- Parse `AndroidManifest.xml` with `androguard`
- Detect permissions, background keep-alive strategies, push integrations, ad SDKs, and common third-party services
- Generate readable Markdown reports for further review

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

You can also run the scripts directly. If required Python packages are missing, the scripts will try to install them automatically. If automatic installation fails, a clear manual install command will be printed.

## Quick Start

Analyze an app by package name:

```bash
python3 android_analyzer.py com.kjvbibleadio.dailyverse
```

Analyze an existing local package:

```bash
python3 android_analyzer.py path/to/app.apk --output reports
```

Download only:

```bash
python3 apkcombo_download.py com.example.app --output downloads
```

Skip download and analyze an existing package in the output directory:

```bash
python3 android_analyzer.py com.example.app --skip-download
```

## Output Files

The analyzer can generate:

- `{package}_analysis.md`
- `{apk_name}_manifest.xml`
- Downloaded `.apk` or `.xapk` packages
- Extracted XAPK directory `{name}_extracted/`

## Project Structure

- `SKILL.md`: Codex skill entry document
- `android_analyzer.py`: Main analysis workflow
- `apkcombo_download.py`: APK/XAPK downloader
- `dependency_bootstrap.py`: Shared dependency bootstrap logic
- `requirements.txt`: Python dependency list
- `tests/`: Unit tests for dependency bootstrap behavior
- `docs/plans/`: Design and implementation notes

## Dependency Handling

This project uses a dual-path dependency strategy:

- Preferred: install dependencies up front with `requirements.txt`
- Fallback: let the script attempt automatic installation on first run

If automatic installation fails, the script prints the exact `pip install` command you need to run manually.

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
