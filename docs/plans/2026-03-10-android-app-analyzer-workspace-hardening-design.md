# Android App Analyzer Workspace Hardening Design

**Goal**

Make the skill reliable for repeated package-based analysis by introducing a managed cache workspace, fixing the APKCombo download flow, and standardizing all in-skill documentation and code comments in English.

**Context**

The current project works for local APK/XAPK inputs, but the package-name download path is fragile because it relies on an outdated APKCombo page parsing strategy. It also writes outputs directly into ad hoc locations, which makes repeated usage hard to control and allows cache growth without guardrails.

**Recommended Approach**

Introduce a shared workspace management layer used by both `android_analyzer.py` and `apkcombo_download.py`. This layer owns cache root resolution, per-package directory creation, threshold enforcement, and stable output paths. The downloader should then be updated to follow APKCombo's current page flow instead of assuming direct download anchors are present in the initial HTML.

## Scope

- Add a required cache workspace root for package-based analysis.
- Store each package under its own child directory named after the package.
- Warn when the number of package child directories exceeds 5.
- Stop execution when the number of package child directories exceeds 20.
- Keep the warning non-blocking and the hard limit blocking.
- Standardize Python comments, CLI messages, and `SKILL.md` guidance in English.
- Improve downloader parsing so it can resolve APKCombo's current variant flow.

## Non-Goals

- Add automatic deletion or background cleanup in this iteration.
- Build a long-term artifact index database.
- Add browser automation as the default download path.
- Expand manifest analysis coverage beyond the current report categories unless it is required by refactoring.

## Workspace Design

Use a deterministic cache root, configurable by CLI but with a safe default inside the repository:

- Default cache root: `.cache/android-app-analyzer/`
- Package workspace: `.cache/android-app-analyzer/<package_name>/`
- Subdirectories:
  - `downloads/`
  - `extracted/`
  - `reports/`
  - `temp/`

For local file analysis, the analyzer can still accept direct APK/XAPK paths, but generated outputs should also land in the managed workspace unless the user explicitly overrides the output root.

The shared workspace layer should:

- sanitize and validate package names before directory creation
- create required subdirectories eagerly
- count only package workspaces, not nested artifact folders
- print a warning when workspace count is greater than 5
- raise a blocking error when workspace count is greater than 20

## Download Flow Design

Replace the old "find direct download link on the download page" logic with the flow observed in current APKCombo pages:

1. Resolve the package search page.
2. Resolve the app page URL.
3. Extract candidate download pages from the app page.
4. Load the selected download page.
5. Extract the internal `xid` token from page script content.
6. POST to `/<xid>/dl` with package metadata.
7. Parse returned variant HTML for `a.variant` download entries.
8. Select a matching APK or XAPK entry.
9. Download via `curl`.

This keeps the implementation browser-free while aligning with the current site structure seen in the debug log.

## File Placement Rules

The package workspace should keep a predictable layout:

- raw package files go to `downloads/`
- extracted base APK files from XAPK go to `extracted/`
- generated manifest XML and Markdown reports go to `reports/`
- transient HTML responses or temporary parsing artifacts go to `temp/`

This makes cleanup obvious and isolates high-value outputs from transient files.

## Error Handling

The skill should fail early with clear guidance in these cases:

- cache root cannot be created
- package workspace count is above the hard limit
- APKCombo page shape changes and `xid` or variant HTML cannot be resolved
- `curl` is unavailable
- dependency bootstrap fails
- XAPK does not contain a usable base APK

The error messages should be action-oriented and English-only. For workspace limit failures, the message should explicitly tell the user to clear the cache root before running the skill again.

## Testing Strategy

Add focused unit tests for the new moving parts:

- workspace directory counting and threshold enforcement
- package workspace path construction
- APKCombo HTML parsing helpers for:
  - `xid` extraction
  - variant link extraction
  - file type detection
- downloader fallback behavior when expected HTML structures are missing

Avoid network-dependent tests. Use stored HTML snippets and pure helper functions wherever possible.

## Additional Improvements Worth Including

- Normalize CLI output formatting so both scripts use consistent phase labels.
- Add a small metadata file in each package workspace, such as `run.json`, to record the package name, timestamp, selected file type, and generated report paths.
- Exclude the cache root from git via `.gitignore`.
- Document a manual cleanup path in both `README` files and `SKILL.md`.

## Trade-Offs

This design adds a thin shared abstraction layer and a few more tests, but it avoids a bigger future refactor. It also intentionally stops short of auto-deletion so the first cache-control version stays predictable and easy to reason about.
