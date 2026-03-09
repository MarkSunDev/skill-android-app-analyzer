# Android App Analyzer Skill Design

**目标**

把当前“脚本集合”整理成标准 Codex skill，同时保留 Python 作为核心实现，并为 GitHub 开源和 npm `skill-source` 发布做好准备。

**设计**

- skill 根目录直接包含 `SKILL.md` 和所有可执行脚本，便于软链接到 `~/.codex/skills`
- 依赖策略采用“双轨制”: 优先自动安装，失败后输出明确的手动安装命令
- 使用 `requirements.txt` 声明 Python 依赖，使用 `package.json` 声明 npm 分发元数据
- 增加最小测试覆盖依赖引导逻辑，确保自动安装和失败提示行为可验证
- README 面向 GitHub 和 npm 用户，`SKILL.md` 面向 Codex 运行时触发

**非目标**

- 不把 Python 逻辑重写成 Node CLI
- 不为 Android 反编译链路引入 Android SDK 或 Java 依赖
