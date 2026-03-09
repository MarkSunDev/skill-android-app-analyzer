---
name: android-app-analyzer
description: Use when analyzing an Android app by package name or local APK/XAPK to inspect manifest metadata, permissions, background keep-alive strategies, push integrations, and ad SDK usage.
---

# Android App Analyzer

## Overview

这个 skill 用于快速分析 Android 应用的 `AndroidManifest.xml`。它支持按包名自动下载 APK/XAPK，也支持直接分析本地安装包，并输出 Markdown 报告。

## When to Use

- 需要快速了解一个 Android 应用的权限声明、组件数量和 SDK 版本
- 需要判断应用是否使用了开机自启、前台服务、精确闹钟、FCM、WorkManager 等后台策略
- 需要排查广告 SDK 或常见第三方服务集成
- 手里只有包名或 APK/XAPK 文件，希望自动生成结构化分析结果

## Quick Start

```bash
python3 android_analyzer.py com.example.app
python3 android_analyzer.py com.example.app --skip-download
python3 android_analyzer.py path/to/app.apk
python3 apkcombo_download.py com.example.app --output downloads
```

## Dependency Handling

- 脚本会在首次运行时尝试自动安装缺失的 Python 依赖
- 自动安装失败时，会打印明确的手动安装命令
- 也可以提前执行:

```bash
python3 -m pip install -r requirements.txt
```

## Outputs

- `{package}_analysis.md`
- `{apk_name}_manifest.xml`
- 下载的 `.apk` 或 `.xapk`
- XAPK 解压目录 `{name}_extracted/`

## Common Mistakes

- `curl` 不可用: 下载器依赖系统 `curl`
- `python` 指向 Python 2: 请显式使用 `python3` 或 Windows 的 `py -3`
- 网络受限: 自动安装依赖和下载 APK 都需要联网
- XAPK 缺少 base APK: 这通常是上游包格式异常，不是 skill 本身的问题
