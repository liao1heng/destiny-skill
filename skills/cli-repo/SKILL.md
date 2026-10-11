---
name: cli-repo
description: 登记当前项目的 GitHub 仓库，并在 macOS 或 Windows 固定 Workspace 目录克隆清单中缺失的项目。适用于“把项目加入 cli-repo”和跨电脑补齐仓库；已有项目不自动拉取、提交或推送。
---

# CLI REPO

共享清单在公开 `liao1heng/destiny-skill` 的 `skills/cli-repo/references/repos.json`，仅保存 GitHub 地址及相对路径。私有项目名称会公开；认证信息和业务凭据不进清单。

- macOS 根目录：`~/Documents/workspace`；Windows 根目录：`D:\Workspace`。
- 默认运行 `scripts/entry.sh` 或 `scripts/entry.ps1`：读取远端最新清单，父项目先克隆、子仓库随后克隆。已有项目只核对位置和远端，不 fetch/pull/commit/push。
- 用户说“把当前项目加入 cli-repo”时运行 `--mode add --project 当前目录`（PowerShell：`-Mode add -Project 当前目录`）。按工作区相对路径和 GitHub 远端登记，再在干净临时 checkout 提交并推送清单。重复登记无变更。
- 如候选远端不唯一，展示候选并请用户指定 `--url` / `-Url`。仅有部署远端、项目不在固定根目录、目录冲突或缺失认证时说明具体问题，不猜地址、不移动/覆盖项目。网络失败不使用可能过时的清单自动克隆。
- `--mode status` / `-Mode status` 只检查远端清单和本机状态，不克隆。正常 clone 模式只补缺失项目；不把“同步仓库”解释为自动提交代码。
- GitHub 认证复用 Git 凭据、环境 token 或 gh 登录；私有库需要对应权限。命令不创建认证文件、不保存 token。Python 或 uv 为 skill 工具依赖，不是业务项目依赖。

新增 skill 和入口通过 cli-sync 受管清单在电脑之间分发；首次在另一台电脑先执行 cli-sync pull，再调用 cli-repo。登记脚本自行更新共享清单，不调用会镜像全部 skill 的 cli-sync push，不提交其他 skill 的本地改动。

```bash
bash ~/.codex/skills/cli-repo/scripts/entry.sh
bash ~/.codex/skills/cli-repo/scripts/entry.sh --mode add --project "$PWD"
```

```powershell
pwsh -File "$HOME\.codex\skills\cli-repo\scripts\entry.ps1"
pwsh -File "$HOME\.codex\skills\cli-repo\scripts\entry.ps1" -Mode add -Project (Get-Location).Path
```

测试：`python3 scripts/test_repo.py`；skill 前置校验使用 skill-creator 的 quick_validate.py。
