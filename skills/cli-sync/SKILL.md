---
name: cli-sync
description: 用于把本机 Codex 自定义 skill 与固定 GitHub 仓库 destiny-skill 同步，执行 git pull / git push，并把仓库内容与本地 ~/.codex/skills 双向同步。适合用户明确要求同步、拉取、推送或镜像 skill 仓库时使用。
---

# CLI SYNC

目标：把固定本地 skill 目录和固定 GitHub 仓库保持同步，不乱猜路径，不临时拼认证。

## 固定路径

- 本地 skill 目录：`C:\Users\the5010_566029155562\.codex\skills`
- 仓库目录：`D:\workspace\sefe_dev\destiny-skill`
- 远端仓库：`https://github.com/liao1heng/destiny-skill.git`
- 分支：`main`
- 认证文件：`C:\Users\the5010_566029155562\.codex\cli-sync\auth.ps1`

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
cli-sync -Mode status
cli-sync -Mode pull
cli-sync -Mode push -Message "Sync local Codex skills"
```

## 注意

- 认证不写进 Git 仓库，只从固定 `auth.ps1` 读取。
- GitHub HTTPS 认证使用 token，不使用 GitHub 账户密码。
- 如果认证文件缺失或字段不完整，先修复认证文件，再执行同步。
