---
name: cli-sync
description: 用于把本机 Codex 自定义 skill 与固定 GitHub 仓库 destiny-skill 零配置同步，执行 git pull / git push，并把仓库内容与本地 ~/.codex/skills 双向同步。适合用户明确要求同步、拉取、推送或镜像 skill 仓库时使用。
---

# CLI SYNC

目标：把本机 Codex skill 和固定 GitHub 仓库保持零配置同步，不写死机器目录，不要求手工建认证文件。

## 自动发现

- 本地 skill 目录：`${CODEX_HOME}/skills`，未设置 `CODEX_HOME` 时回退到 `~/.codex/skills`
- 仓库目录按顺序自动确定：
- 如果脚本本身就在 `destiny-skill` 仓库里，直接用当前仓库
- 如果当前工作目录就在 `destiny-skill` 仓库里，直接用当前仓库
- 否则使用 `${CODEX_HOME}/repos/destiny-skill`
- 如果 `${CODEX_HOME}/repos/destiny-skill` 不存在，就自动 clone
- 远端仓库：`https://github.com/liao1heng/destiny-skill.git`
- 分支：`main`
- GitHub 认证自动探测：优先复用当前机器已有的 GitHub 凭据、环境变量 token 或 SSH 远端

## 受管 skill

- `cli-arc`
- `cli-des`
- `cli-dev`
- `cli-init`
- `cli-pm`
- `cli-sync`
- `cli-test`
- `figma`

## 工作流

1. 先执行 `scripts\entry.ps1 -Mode status` 看当前仓库状态。
2. 需要把 GitHub 最新内容覆盖到本机 skill 时，执行 `-Mode pull`。
3. 需要把本机 skill 更新推到 GitHub 时，执行 `-Mode push -Message "..."`
4. `push` 以本机 `~/.codex/skills` 为准：先拉远端，再把受管 skill 镜像进仓库，最后 commit + push。
5. `pull` 以 GitHub 仓库为准：先拉远端，再把仓库里的受管 skill 镜像到本机 skill 目录。

## 命令

```powershell
pwsh -File skills/cli-sync/scripts/entry.ps1 -Mode status
pwsh -File skills/cli-sync/scripts/entry.ps1 -Mode pull
pwsh -File skills/cli-sync/scripts/entry.ps1 -Mode push -Message "Sync local Codex skills"
```

```bash
bash skills/cli-sync/scripts/entry.sh --mode status
bash skills/cli-sync/scripts/entry.sh --mode pull
bash skills/cli-sync/scripts/entry.sh --mode push --message "Sync local Codex skills"
```

## 注意

- 支持 Windows 和 macOS；核心逻辑使用 Python。
- 不需要再创建 `auth.ps1` 或机器路径配置。
- GitHub HTTPS 认证使用 token，不使用 GitHub 账户密码。
