# Codex Skill: Android App Analyzer

`android-app-analyzer` 是一个可发布的 Codex skill 源码包，用来分析 Android APK/XAPK 或按包名下载并生成 Manifest 报告。

## 能力概览

- 按包名从 apkcombo 下载 APK/XAPK
- 自动解压 XAPK 并提取 base APK
- 使用 `androguard` 解析 `AndroidManifest.xml`
- 检测权限、后台保活策略、推送方案、广告 SDK 和常见第三方服务
- 输出 Markdown 分析报告

## 目录结构

- `SKILL.md`: Codex skill 入口说明
- `android_analyzer.py`: 主分析脚本
- `apkcombo_download.py`: APK/XAPK 下载器
- `dependency_bootstrap.py`: Python 依赖自动安装与失败提示
- `requirements.txt`: 手动安装依赖时使用
- `tests/`: 依赖引导逻辑测试

## 本地使用

### 1. 先安装依赖

```bash
python3 -m pip install -r requirements.txt
```

也可以直接运行脚本。脚本会在发现依赖缺失时尝试自动安装；如果自动安装失败，会打印明确的手动安装命令。

### 2. 运行分析

```bash
python3 android_analyzer.py com.kjvbibleadio.dailyverse
python3 android_analyzer.py com.example.app --skip-download
python3 android_analyzer.py path/to/app.apk --output reports
python3 apkcombo_download.py com.example.app --output downloads
```

如果你在 Windows 上发现 `python` 指向 Python 2，请显式使用 `python3` 或 `py -3`。

## 安装到 Codex Skill 库

建议使用软链接把当前项目直接挂到本地 skill 库：

```powershell
New-Item -ItemType SymbolicLink `
  -Path "$HOME\\.codex\\skills\\android-app-analyzer" `
  -Target "C:\\path\\to\\this\\project"
```

## npm 包定位

这个包按 `skill-source` 思路分发，重点是交付 skill 文件和 Python 实现，而不是把 Python 逻辑重新包装成 Node CLI。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
