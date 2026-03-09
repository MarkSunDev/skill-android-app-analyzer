# README Internationalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the default repository README with a polished English open source README and add a matching Simplified Chinese version with language switch links.

**Architecture:** Keep `README.md` as the default English landing page for GitHub and npm users. Add `README.zh-CN.md` as the Chinese companion document, and keep both files aligned in section structure so the repository feels consistent and maintainable.

**Tech Stack:** Markdown, GitHub README conventions

---

### Task 1: Rewrite the default README

**Files:**
- Modify: `README.md`

**Step 1: Add language switch links**

Place `English | 简体中文` at the top and make the Chinese link point to `README.zh-CN.md`.

**Step 2: Replace the current localized content**

Rewrite the README in English using a standard open source structure: overview, features, requirements, installation, quick start, outputs, project structure, Codex skill install, npm package, testing, license.

### Task 2: Add the Chinese companion README

**Files:**
- Create: `README.zh-CN.md`

**Step 1: Mirror the English structure**

Keep the same sections and order so both documents remain easy to maintain.

**Step 2: Add reciprocal language links**

Make the top bar link back to `README.md`.

### Task 3: Verify documentation changes

**Files:**
- Modify: `README.md`
- Create: `README.zh-CN.md`

**Step 1: Review diff**

Run `git diff -- README.md README.zh-CN.md` to verify the content is limited to README internationalization.

**Step 2: Review status**

Run `git status --short` to confirm the exact changed files.
