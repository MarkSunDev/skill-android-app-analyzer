# Android App Analyzer Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把当前项目重构成标准 Codex skill，并补齐 GitHub / npm 发布所需的最小工程文件。

**Architecture:** skill 根目录直接作为发布单元，Python 脚本负责下载和分析逻辑，共享一个依赖引导模块；文档层拆分为 `SKILL.md`、README 和计划文档；npm 包只分发 skill 源码与脚本，不额外引入 Node 运行时包装。

**Tech Stack:** Python 3.8+, pip, unittest, npm metadata, Git, Windows symbolic link

---

### Task 1: 标准化 skill 目录

**Files:**
- Create: `SKILL.md`
- Create: `README.md`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `package.json`

**Step 1: 写入 skill 入口文档**

明确触发条件、依赖策略和常用命令。

**Step 2: 拆分面向 GitHub / npm 的 README**

把“skill 如何被触发”和“项目如何使用/发布”分开。

**Step 3: 补齐发布元数据**

增加 `requirements.txt`、MIT License、npm `publishConfig`。

### Task 2: 重构依赖安装逻辑

**Files:**
- Create: `dependency_bootstrap.py`
- Modify: `android_analyzer.py`
- Modify: `apkcombo_download.py`
- Test: `tests/test_dependency_bootstrap.py`

**Step 1: 先写失败场景测试**

覆盖“无需安装”“安装后成功”“安装失败提示清晰”三种情况。

**Step 2: 抽取公共依赖引导模块**

统一处理自动安装和失败提示，避免两个脚本各自实现。

**Step 3: 更新两个脚本接入公共模块**

保持现有业务逻辑不变，只改依赖入口和错误提示。

### Task 3: 本地安装与发布准备

**Files:**
- Create: `docs/plans/2026-03-09-android-app-analyzer-skill-design.md`
- Create: `docs/plans/2026-03-09-android-app-analyzer-skill.md`

**Step 1: 运行 Python 测试和帮助命令**

验证脚本和打包元数据。

**Step 2: 创建本地软链接**

把当前目录挂载到 `C:\\Users\\cm\\.codex\\skills\\android-app-analyzer`。

**Step 3: 初始化 git 并准备 GitHub / npm 发布**

若 SSH 或 npm 登录异常，保留清晰的阻塞信息与后续命令。
