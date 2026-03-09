# Android App Analyzer Workspace Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add managed cache workspaces, harden APKCombo package downloads, and standardize skill-facing documentation and code comments in English.

**Architecture:** Introduce a shared workspace utility module that both entry scripts use for cache root resolution, package workspace creation, threshold checks, and output path selection. Refactor the APKCombo downloader into small parsing helpers so the current page flow can be tested without live network access. Keep existing manifest analysis logic mostly intact while moving outputs into the managed workspace layout.

**Tech Stack:** Python 3, `requests`, `beautifulsoup4`, `androguard`, `unittest`, `curl`, Markdown documentation, Git

---

### Task 1: Add workspace management tests

**Files:**
- Create: `tests/test_workspace_manager.py`

**Step 1: Write a failing test for default workspace path creation**

Add a test that creates a temporary repository-like root, resolves the default cache root, and asserts the expected `.cache/android-app-analyzer` path is created.

**Step 2: Run the new test to confirm it fails**

Run: `python -m unittest tests.test_workspace_manager -v`
Expected: FAIL because the workspace helper does not exist yet.

**Step 3: Write a failing test for the warning threshold**

Add a test that creates 6 package child directories and asserts the helper reports a warning state without raising.

**Step 4: Write a failing test for the hard limit**

Add a test that creates 21 package child directories and asserts the helper raises a blocking workspace limit error.

**Step 5: Commit**

```bash
git add tests/test_workspace_manager.py
git commit -m "test: add workspace manager coverage"
```

### Task 2: Implement the shared workspace manager

**Files:**
- Create: `workspace_manager.py`
- Modify: `.gitignore`

**Step 1: Implement cache root resolution**

Create a helper that resolves the default cache root to `.cache/android-app-analyzer` relative to the repository and creates it when missing.

**Step 2: Implement package workspace creation**

Add a helper that validates the package name, creates the package folder, and creates `downloads`, `extracted`, `reports`, and `temp` subdirectories.

**Step 3: Implement threshold enforcement**

Add a helper that counts package child directories, returns warning messages above 5, and raises a dedicated error above 20.

**Step 4: Ignore cache artifacts in git**

Update `.gitignore` to exclude `.cache/`.

**Step 5: Run workspace tests**

Run: `python -m unittest tests.test_workspace_manager -v`
Expected: PASS

**Step 6: Commit**

```bash
git add workspace_manager.py .gitignore tests/test_workspace_manager.py
git commit -m "feat: add managed analyzer workspace"
```

### Task 3: Add downloader parser tests

**Files:**
- Create: `tests/test_apkcombo_download.py`

**Step 1: Write a failing test for `xid` extraction**

Use a saved HTML snippet containing `var xid = "..."` and assert the parser extracts the expected token.

**Step 2: Write a failing test for variant extraction**

Use a saved HTML fragment from the `/<xid>/dl` response and assert the parser returns at least one structured variant entry.

**Step 3: Write a failing test for file type classification**

Assert that XAPK and APK variants are classified correctly from text and URL hints.

**Step 4: Run the downloader parser tests**

Run: `python -m unittest tests.test_apkcombo_download -v`
Expected: FAIL because the helper functions do not exist yet.

**Step 5: Commit**

```bash
git add tests/test_apkcombo_download.py
git commit -m "test: cover apkcombo parser helpers"
```

### Task 4: Refactor `apkcombo_download.py` around testable helpers

**Files:**
- Modify: `apkcombo_download.py`

**Step 1: Extract HTML parsing helpers**

Create small pure functions for:
- extracting `xid`
- parsing variant links from returned HTML
- selecting a preferred variant
- deriving file names and file types

**Step 2: Update the network flow**

Replace the current direct variant scraping logic with:
- app page discovery
- selected download page fetch
- `xid` extraction
- POST to `/<xid>/dl`
- variant parsing

**Step 3: Move output placement into the package workspace**

Write downloads into the shared `downloads/` directory returned by the workspace manager.

**Step 4: Standardize logs and inline comments in English**

Convert mixed-language output and comments to concise English.

**Step 5: Run the downloader tests**

Run: `python -m unittest tests.test_apkcombo_download -v`
Expected: PASS

**Step 6: Commit**

```bash
git add apkcombo_download.py tests/test_apkcombo_download.py
git commit -m "feat: harden apkcombo download flow"
```

### Task 5: Update analyzer workflow to use managed workspaces

**Files:**
- Modify: `android_analyzer.py`

**Step 1: Route package-name analysis through the workspace manager**

When the target is a package name, resolve the package workspace before download and enforce the cache thresholds.

**Step 2: Route local file analysis outputs into managed report paths**

Store extracted APKs, manifest XML, and Markdown reports in workspace subdirectories instead of the repository root.

**Step 3: Emit warning messages without blocking when workspace count is above 5**

Print the warning once near startup and continue execution.

**Step 4: Fail fast above the hard limit**

Raise the workspace limit error before any download attempt.

**Step 5: Convert comments, phase labels, and user-facing messages to English**

Keep them short and consistent with the downloader.

**Step 6: Run focused analyzer smoke checks**

Run:
- `python android_analyzer.py --help`
- `python apkcombo_download.py --help`

Expected: both commands exit successfully with English help text.

**Step 7: Commit**

```bash
git add android_analyzer.py
git commit -m "feat: route analyzer outputs into managed workspace"
```

### Task 6: Standardize shared dependency messages

**Files:**
- Modify: `dependency_bootstrap.py`
- Modify: `tests/test_dependency_bootstrap.py`

**Step 1: Update dependency bootstrap messages to English**

Convert installation progress and failure guidance strings to English-only output.

**Step 2: Update tests for the new message text**

Replace Chinese assertion text with English expectations.

**Step 3: Run dependency bootstrap tests**

Run: `python -m unittest tests.test_dependency_bootstrap -v`
Expected: PASS

**Step 4: Commit**

```bash
git add dependency_bootstrap.py tests/test_dependency_bootstrap.py
git commit -m "refactor: standardize dependency bootstrap messages"
```

### Task 7: Update skill and repository documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Step 1: Update `SKILL.md` to describe the managed workspace**

Document the cache root, package subdirectory behavior, warning threshold, hard limit, and manual cleanup expectation in English.

**Step 2: Update `README.md`**

Document the new workspace layout, file placement rules, and current APKCombo assumptions.

**Step 3: Update `README.zh-CN.md`**

Keep the README in Chinese where appropriate, but describe code-level and skill-level English standardization accurately.

**Step 4: Commit**

```bash
git add SKILL.md README.md README.zh-CN.md
git commit -m "docs: document managed workspace behavior"
```

### Task 8: Run final verification

**Files:**
- Verify only

**Step 1: Run all unit tests**

Run: `python -m unittest discover -s tests -v`
Expected: PASS

**Step 2: Run CLI help checks again**

Run:
- `python android_analyzer.py --help`
- `python apkcombo_download.py --help`

Expected: PASS

**Step 3: Perform one dry-run package workflow review**

Review the startup path manually or with mocks to confirm:
- package workspace is created
- threshold warning appears above 5
- hard limit stops execution above 20

**Step 4: Commit**

```bash
git add .
git commit -m "chore: finalize workspace hardening changes"
```
