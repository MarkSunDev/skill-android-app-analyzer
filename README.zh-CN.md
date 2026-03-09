[English](README.md) | [简体中文](README.zh-CN.md)

# Android App Analyzer

这是一个面向 Codex 的 skill 源码包，用于下载 Android APK/XAPK、解析 Manifest 信息，并生成结构化分析报告，适合竞品分析、SDK 排查和基础研究场景。

## 功能特性

- 按包名从 apkcombo 下载最新 APK 或 XAPK
- 自动从 XAPK 中提取 base APK
- 使用 `androguard` 解析 `AndroidManifest.xml`
- 检测权限、后台保活策略、推送集成、广告 SDK 和常见第三方服务
- 生成便于后续审阅的 Markdown 报告

## 项目定位

这个项目用于在不依赖完整 Android SDK 工具链的前提下，快速、可脚本化地分析 Android 安装包。它尤其适合产品研究、增长分析、广告变现分析和轻量级安全检查。

## 环境要求

- Python 3.8 或更高版本
- `curl`
- 用于安装依赖和下载安装包的网络环境

如果 Windows 上的 `python` 指向 Python 2，请显式使用 `python3` 或 `py -3`。

## 安装

### 安装为 Codex Skill（推荐）

推荐直接通过 GitHub 仓库配合 skills CLI 安装：

```bash
npx skills add MarkSunDev/skill-android-app-analyzer -g -y
```

这是普通用户最推荐的安装方式。

### 手动安装 Python 依赖

推荐先手动安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

你也可以直接运行脚本。若缺少 Python 依赖，脚本会先尝试自动安装；若自动安装失败，会输出清晰的手动安装命令。

## 快速开始

按包名分析应用：

```bash
python3 android_analyzer.py com.kjvbibleadio.dailyverse
```

分析本地已有安装包：

```bash
python3 android_analyzer.py path/to/app.apk --output reports
```

只下载，不分析：

```bash
python3 apkcombo_download.py com.example.app --output downloads
```

跳过下载，直接分析输出目录里已有的安装包：

```bash
python3 android_analyzer.py com.example.app --skip-download
```

## 输出文件

分析器可能生成以下文件：

- `{package}_analysis.md`
- `{apk_name}_manifest.xml`
- 下载得到的 `.apk` 或 `.xapk`
- XAPK 解压目录 `{name}_extracted/`

## 项目结构

- `SKILL.md`: Codex skill 入口说明
- `android_analyzer.py`: 主分析流程
- `apkcombo_download.py`: APK/XAPK 下载器
- `dependency_bootstrap.py`: 共享依赖引导逻辑
- `requirements.txt`: Python 依赖列表
- `tests/`: 依赖引导逻辑的单元测试
- `docs/plans/`: 设计与实现说明

## 依赖处理策略

这个项目采用双轨依赖策略：

- 推荐方式：提前通过 `requirements.txt` 安装依赖
- 兜底方式：脚本首次运行时尝试自动安装缺失依赖

如果自动安装失败，脚本会打印出可直接执行的 `pip install` 命令。

## 安装到 Codex Skill 库（本地开发）

如果你想把当前项目直接挂到本地 Codex skill 库，可以创建软链接：

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$HOME\\.codex\\skills\\android-app-analyzer" `
  -Target "C:\\path\\to\\this\\project"
```

## npm 包说明

这个仓库按 `skill-source` 形式发布 npm 包。npm 包的目标是分发 Codex skill 文件和 Python 实现，但它不是普通用户的主要安装入口。

这个项目的推荐安装命令是：

```bash
npx skills add MarkSunDev/skill-android-app-analyzer -g -y
```

不要对这个项目使用 `npx skill ...` 这类无关命令，因为那会调用另一个 npm 包，并不是当前仓库的安装方式。

## 测试

运行单元测试：

```bash
python3 -m unittest discover -s tests -v
```

## License

基于 MIT License 发布。
