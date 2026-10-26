---
name: cli-jira
description: 通过 HTTP 请求查询 Jira 问题、读取备注和附件、添加备注或更新问题状态，不用浏览器逐条操作。用于 Jira 链接排查、缺陷修复后的状态更新及批量处理，适用于任意项目目录。
---

# CLI Jira

使用随附 `scripts/jira.py` 直接访问 Jira REST API，无第三方 Python 依赖。默认站点为 `http://jira.slimxu.com:8080`；不限于某个业务仓库，不依赖 `fix-jira` 工作目录。

## 认证

- 默认读取本机 `~/.config/cli-jira/config.json`；Windows 有 `APPDATA` 时读取 `%APPDATA%/cli-jira/config.json`。
- 配置字段为 `JIRA_BASE_URL` 和 `JIRA_COOKIE`。`JIRA_CONFIG` 可指定另一配置文件，同名环境变量可覆盖地址和 Cookie。
- 用户提供 Copy as cURL 时，提取目标地址和 Cookie 写入本机配置（权限尽量设为 600），不要直接执行其中的示例 POST。
- 凭证放在 skill 目录和 Git 仓库之外，不打印 Cookie，不把带凭证的请求或本机配置同步到 GitHub。
- 先执行 `me` 检查登录。401、登录重定向或 HTML 登录页表示需要更新 Cookie；不反复重试，不自动转用浏览器操作状态。

## 调用

将下列路径替换为当前 skill 所在目录，使用可用的 Python 3：

```sh
python3 <skill-directory>/scripts/jira.py me
python3 <skill-directory>/scripts/jira.py get HSHY-76344
python3 <skill-directory>/scripts/jira.py comments HSHY-76344 --start 0 --limit 100
python3 <skill-directory>/scripts/jira.py download HSHY-76344 253151 --directory /tmp/jira-attachments
python3 <skill-directory>/scripts/jira.py search 'assignee = currentUser() AND resolution = Unresolved ORDER BY updated DESC'
python3 <skill-directory>/scripts/jira.py transitions HSHY-76344
```

`get` 默认包含描述、附件和备注，可用 `--fields` 缩小字段。`search` 和 `comments` 每页最多 100 条；根据响应中的 `total`、`startAt` 和实际返回条数读取后续页。备注中的截图可能在描述之外，检查备注及附件；下载后使用图像查看工具读取图片。下载命令只接受该问题实际返回的附件 ID，不向不同源地址转发认证。

## 修改 Jira

修复代码与更新 Jira 状态是两项操作，按用户要求的范围和顺序执行。用户明确要求发送备注或标记解决后，直接执行，无需重复询问；仅提供请求样例或要求创建 skill 时不发送样例内容。未获要求时不额外评论、不更改经办人。

```sh
python3 <skill-directory>/scripts/jira.py comment HSHY-76344 --body '用户要求发送的实际备注内容'
python3 <skill-directory>/scripts/jira.py transition HSHY-76344 --id '当前查询返回的动作ID'
```

- 添加备注使用 `/rest/api/2/issue/{key}/comment`；更新状态使用 `/rest/api/2/issue/{key}/transitions`，两者不可混用。
- 每次流转前查询当前 `transitions`。按动作名称及 `to` 选择目标；ID 不跨问题或工作流硬编码。也可用 `--name` 精确匹配唯一动作。
- 必填字段和允许值以 `transitions.fields` 为准。需要时写入临时 JSON 字段对象，通过 `--fields-file` 传入，不猜测 resolution ID。
- 如果到达目标需要正常的中间流转（如“开始进行”），在用户授权的目标内执行一步，回读后重新查询下一步；不尝试与目标无关的关闭、转交等动作。没有合理可用路径时报告具体阻碍。
- 写请求不自动重试。超时或回读失败时先查询实际状态/备注，确认原请求是否生效，避免重复发送。脚本输出的 `verified` 表示回读状态是否匹配目标。

## 批量处理与缺陷修复

- 先建立明确的问题编号清单。用户说“已修复的 bug”时从本次修复记录、提交或验收清单确定范围，不将整个未解决筛选器视为已修复。
- 更新每条前查询状态；已达到用户要求的目标则跳过。单条失败保留结果，继续不依赖它的其他问题；认证整体失效时停止发送。
- 最后报告成功、已完成、失败的编号和原因；回读状态与解决结果后再宣称解决。
- 涉及源码时遵循对应项目的 AGENTS.md 和用户约定的提交、推送、页面验收顺序。API 状态检查不能代替实际页面验收。
