# Skills Add Installation Support Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the repository clearly support installation through `npx skills add MarkSunDev/skill-android-app-analyzer` and reduce confusion with npm and unrelated `npx skill` commands.

**Architecture:** The repository already exposes a valid root `SKILL.md`, so the functional support exists. The required change is documentation: promote `npx skills add` as the primary install path, keep symlink installation as the local development path, and explicitly state that the npm package is not a direct executable CLI.

**Tech Stack:** Markdown, GitHub README conventions, skills CLI

---

### Task 1: Clarify the primary install path

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Step 1: Add a recommended install section**

Document `npx skills add MarkSunDev/skill-android-app-analyzer -g -y` as the preferred user install command.

**Step 2: Distinguish local development installation**

Keep symlink installation for contributors and local debugging only.

### Task 2: Remove npm installation ambiguity

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Step 1: Explain what the npm package is**

Describe it as a distribution artifact, not the primary end-user install path.

**Step 2: Call out incorrect commands**

State that `npx skill ...` targets a different package and should not be used for this repository.
