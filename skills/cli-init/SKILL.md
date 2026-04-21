---
name: cli-init
description: 为项目初始化或修正基础协作与部署规范。用于创建或更新 AGENTS.md、补齐根说明文件、建立 git push 到服务器 post-receive 的发布流程，并固定使用 Prisma、PM2 和 updateDB 约定。执行前先探测真实目录、说明文件、git remote 和 hook；如果服务器信息、远端路径、入口文件、PM2 进程名或 prisma/mr.sh 无法确定，就停下来询问用户。
---

# CLI INIT

目标：把项目初始化成统一可维护状态，不乱猜，不写废话。

## 固定约定

- 部署固定为：`git push` -> 服务器仓库 `post-receive` -> 更新代码。
- 进程固定用 `PM2`。
- 数据库固定用 `Prisma`。
- commit message 含 `updateDB` 时执行数据库更新。
- 默认数据库脚本是 `prisma/mr.sh`。
- `AGENTS.md` 固定写：代码尽量精简、优先复用公共模块、高内聚低耦合。
- 只有检测到 `cli-des` 产物时，才补设计规范规则。
- 如果根说明文件已经明文记录服务器信息、账号、密码或手工同步方式，默认视为项目显式约定，保留原格式，不自行删除，不额外加安全说教。
- 根说明文件里的部署说明默认只写一句话：推送到指定远端/分支后会自动部署。执行细节写到脚本、模板或 `AGENTS.md`，不要把 hook 过程展开成大段说明。

## 先检查

1. 根说明文件，按顺序读：
- `readme.txt`
- `README.md`
- `README.txt`
- `readme.md`

2. 实际目录和入口：
- 服务入口
- 前端目录
- 后台目录
- `prisma/`
- 部署脚本
- `.git/hooks/post-receive`

3. git 与部署：
- `git remote -v`
- `.git/config`
- 现有 `post-receive`
- 现有远端推送方式

4. 当前目录说明文件：
- 改代码前优先读当前目录的 `readme.txt`、`README.md`、`README.txt`、`readme.md`

## 要做的事

- 有 `AGENTS.md` 就补全，没有就创建。
- 根说明文件缺部署规则就补上；默认补成一句话，不把脚本执行细节堆进根说明文件。
- 根说明文件已有服务器信息时，按原有写法保留；如果探测到的新服务器信息和根说明冲突，先问用户，不直接覆盖。
- 仓库内保留一份可追踪的 `post-receive` 模板。
- 远端真实 hook 要和模板一致。
- hook 至少包含：
- 依赖文件变更时安装依赖
- `npx prisma generate`
- commit message 含 `updateDB` 时执行 `bash prisma/mr.sh`
- 重启 PM2 进程

## 写 AGENTS.md 时固定写

- 先读根说明文件。
- 改代码前先读当前目录说明文件。
- 代码尽量精简，优先复用公共模块。
- 功能变更时同步更新对应目录说明文件。
- 目录结构以实际仓库为准，不照搬旧项目。

## `cli-des` 条件规则

只有存在以下文件之一时，才补“先读设计规范”：

- `design-theme.json`
- `DESIGN_GUIDE.md`
- `design-tokens.css`
- `motion-tokens.css`
- `tailwind.design.preset.js`

## 这些情况必须停下问用户

- 连不上服务器
- 远端仓库或部署目录不清楚
- 找不到 `prisma/mr.sh`
- 找不到 PM2 进程名
- 多个入口文件无法判断
- 根说明文件和实际目录冲突严重
- 根说明文件里的服务器信息与实际探测结果冲突

## 验证

- `AGENTS.md` 和实际目录一致
- 根说明文件包含部署规则
- 仓库模板和远端 `post-receive` 一致
- `updateDB` 分支和 PM2 重启命令可落地
