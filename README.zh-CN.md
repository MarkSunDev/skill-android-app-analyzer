[English](README.md) | [简体中文](README.zh-CN.md)

# Android App Analyzer

这是一个同时兼容 Claude Code marketplace、Codex 和 Gemini CLI 扩展机制的 skill 源码包，用于下载 Android APK/XAPK、解析 Manifest 信息，并生成结构化分析报告，适合竞品分析、SDK 排查和基础研究场景。

## 功能特性

- 按包名从 APKCombo 下载最新 APK 或 XAPK
- 使用受控缓存工作空间管理重复运行
- 自动从 XAPK 中提取 base APK
- 使用 `androguard` 解析 `AndroidManifest.xml`
- 检测权限、后台保活策略、推送集成、广告 SDK 和常见第三方服务
- 生成 Markdown 报告和运行元数据，便于后续审阅

## 项目定位

这个项目用于在不依赖完整 Android SDK 工具链的前提下，快速、可脚本化地分析 Android 安装包。它尤其适合产品研究、增长分析、广告变现分析和轻量级安全检查。

## 环境要求

- Python 3.8 或更高版本
- `curl`
- 用于安装依赖和下载安装包的网络环境

如果 Windows 上的 `python` 指向 Python 2，请显式使用 `python3` 或 `py -3`。

## 安装

### 安装为 Claude Code Marketplace Plugin

当前仓库已经补充了根目录 `.claude-plugin/marketplace.json`，可以直接作为 Claude Code 的 marketplace 仓库添加：

```bash
/plugin marketplace add MarkSunDev/skill-android-app-analyzer
/plugin install android-app-analyzer@marksundev-skills
```

其中 marketplace 名称是 `marksundev-skills`，插件名是 `android-app-analyzer`。

### 使用 Dvcode AI 安装

先添加仓库 marketplace，再安装插件：

```bash
/skill marketplace add https://github.com/MarkSunDev/skill-android-app-analyzer
/plugin install skill-android-app-analyzer:android-app-analyzer
```

### 安装为 Codex Skill（推荐）

推荐直接通过 GitHub 仓库配合 skills CLI 安装：

```bash
npx skills add MarkSunDev/skill-android-app-analyzer -g -y
```

这是普通用户最推荐的安装方式。

### 安装为 Gemini CLI Extension

当前仓库已包含根目录 `gemini-extension.json`，可以直接作为 Gemini CLI 扩展安装：

```bash
gemini extensions install https://github.com/MarkSunDev/skill-android-app-analyzer
```

本地开发时，也可以从绝对路径安装或软链接：

```bash
gemini extensions install /absolute/path/to/skill-android-app-analyzer
gemini extensions link /absolute/path/to/skill-android-app-analyzer
```

如果要校验当前仓库的扩展清单，可执行：

```bash
gemini extensions validate .
```

### 手动安装 Python 依赖

推荐先手动安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

脚本也支持懒加载依赖。只有真正走到下载或分析路径时，才会尝试安装对应依赖；如果自动安装失败，会输出可直接执行的手动安装命令。

## 受控工作空间

分析器默认使用受控缓存工作空间：

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

规则如下：

- 当包级子目录数量大于 `5` 时：只告警，不阻断流程。
- 当包级子目录数量大于 `20` 时：直接中断，要求先手动清理。

当前版本不会自动删除旧目录，清理动作由用户显式执行。`SKILL.md`、Python 注释和 CLI 文案现在统一使用英文，避免 skill 运行时出现中英文混杂。

## 快速开始

按包名分析应用：

```bash
python3 android_analyzer.py com.kjvbibleadio.dailyverse
```

分析本地已有安装包：

```bash
python3 android_analyzer.py path/to/app.apk
```

只下载，不分析：

```bash
python3 apkcombo_download.py com.example.app
```

指定自定义工作空间根目录：

```bash
python3 android_analyzer.py com.example.app --output D:\analysis-cache
```

跳过下载，复用工作空间里已有的缓存包：

```bash
python3 android_analyzer.py com.example.app --skip-download
```

## 输出文件

分析器可能生成以下内容：

- `downloads/*.apk` 或 `downloads/*.xapk`
- `extracted/<xapk-name>/...`
- `reports/{package}_analysis.md`
- `reports/{apk_name}_manifest.xml`
- `run.json`

## APKCombo 下载链路说明

下载器现在按 APKCombo 的当前页面结构工作：

1. 打开解析后的应用页。
2. 找到下载页。
3. 从页面脚本中提取内部 `xid`。
4. 向 `/<xid>/dl` 发起 POST。
5. 解析返回的变体链接。
6. 使用 `curl` 下载最终 APK/XAPK。

如果 APKCombo 后续再次调整页面结构，优先检查和更新 `apkcombo_download.py`。

## 项目结构

- `.claude-plugin/marketplace.json`: Claude Code marketplace 定义文件
- `gemini-extension.json`: Gemini CLI 扩展清单文件
- `SKILL.md`: Codex skill 入口说明
- `android_analyzer.py`: 主分析流程
- `apkcombo_download.py`: APK/XAPK 下载器
- `workspace_manager.py`: 共享工作空间管理逻辑
- `dependency_bootstrap.py`: 共享依赖引导逻辑
- `requirements.txt`: Python 依赖列表
- `tests/`: 工作空间、下载解析和依赖引导的单元测试
- `docs/plans/`: 设计与实现说明

## 安装到 Codex Skill 库（本地开发）

如果你想把当前项目直接挂到本地 Codex skill 库，可以创建软链接：

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$HOME\\.codex\\skills\\android-app-analyzer" `
  -Target "C:\\path\\to\\this\\project"
```

## npm 包说明

这个仓库按 `skill-source` 形式发布 npm 包。npm 包的目标是分发 Codex skill 文件和 Python 实现，但它不是普通用户的主要安装入口。

推荐安装命令：

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
