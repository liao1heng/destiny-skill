#!/usr/bin/env python3
"""Jira REST CLI. Credentials are loaded locally and never printed."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

def config_path():
    if os.environ.get('JIRA_CONFIG'):
        return Path(os.environ['JIRA_CONFIG']).expanduser()
    base = Path(os.environ.get('APPDATA') or Path.home() / '.config')
    return base / 'cli-jira' / 'config.json'


class JiraError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward a manually supplied Cookie to a redirected destination.
        return None


def configuration():
    config = {}
    path = config_path()
    if path.exists():
        config = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(config, dict):
            raise JiraError('Jira 配置必须为 JSON 对象。')
    config.update({k: os.environ[k] for k in ('JIRA_BASE_URL', 'JIRA_COOKIE') if k in os.environ})
    if not config.get('JIRA_COOKIE'):
        raise JiraError(f'缺少 JIRA_COOKIE，请更新本机配置 {path} 或环境变量。')
    return config.get('JIRA_BASE_URL', 'http://jira.slimxu.com:8080').rstrip('/'), config['JIRA_COOKIE']


class Jira:
    def __init__(self):
        self.base, self.cookie = configuration()
        self.opener = build_opener(NoRedirect())

    def request(self, path, data=None):
        headers = {
            'Cookie': self.cookie,
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.base,
        }
        body = None
        if data is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = Request(self.base + '/rest/api/2/' + path, data=body, headers=headers)
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read()
                if not raw:
                    return None
                if 'json' not in response.headers.get('Content-Type', '').lower():
                    raise JiraError('服务器未返回 JSON，登录可能已失效。')
                return json.loads(raw)
        except HTTPError as error:
            if error.code in (301, 302, 303, 307, 308, 401):
                raise JiraError(f'HTTP {error.code}：登录失效或被重定向，请更新 Cookie。') from None
            try:
                detail = json.loads(error.read())
                detail = {'errorMessages': detail.get('errorMessages'), 'errors': detail.get('errors')}
            except (ValueError, AttributeError):
                detail = '服务器拒绝请求'
            raise JiraError(f'HTTP {error.code}: {json.dumps(detail, ensure_ascii=False)}') from None
        except URLError as error:
            raise JiraError(f'连接失败：{error.reason}') from None

    def issue(self, key, fields='summary,status,resolution,assignee,updated'):
        return self.request(f'issue/{quote(key)}?' + urlencode({'fields': fields}))

    def transitions(self, key):
        return self.request(f'issue/{quote(key)}/transitions?expand=transitions.fields')['transitions']

    def download(self, key, attachment_id, directory):
        attachments = self.issue(key, 'attachment')['fields'].get('attachment', [])
        attachment = next((item for item in attachments if str(item['id']) == attachment_id), None)
        if not attachment:
            raise JiraError('该附件不属于指定问题。')
        url = attachment['content']
        target, source = urlsplit(url), urlsplit(self.base)
        if (target.scheme, target.netloc) != (source.scheme, source.netloc):
            raise JiraError('附件地址与 Jira 不同源，不向其转发 Cookie。')
        name = Path(attachment['filename'].replace('\\', '/')).name
        output = directory / f'{attachment_id}-{name}'
        directory.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={'Cookie': self.cookie})
        try:
            with self.opener.open(request, timeout=30) as response:
                if 'text/html' in response.headers.get('Content-Type', '').lower() and attachment.get('mimeType') != 'text/html':
                    raise JiraError('附件返回了 HTML，登录可能失效。')
                content = response.read()
            with output.open('xb') as saved:
                saved.write(content)
        except HTTPError as error:
            raise JiraError(f'附件下载失败：HTTP {error.code}，未自动重试。') from None
        except URLError as error:
            raise JiraError(f'附件下载失败：{error.reason}') from None
        return {'key': key, 'attachmentId': attachment_id, 'path': str(output.resolve())}


def issue_key(value):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*-\d+', value):
        raise argparse.ArgumentTypeError('问题编号应类似 HSHY-76344')
    return value.upper()


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('me', help='只读检查当前登录')
    for name in ('get', 'transitions'):
        sub = commands.add_parser(name)
        sub.add_argument('key', type=issue_key)
        if name == 'get':
            sub.add_argument('--fields', default='summary,description,status,resolution,assignee,updated,attachment,comment')
    comments = commands.add_parser('comments', help='分页读取备注')
    comments.add_argument('key', type=issue_key)
    comments.add_argument('--start', type=int, default=0)
    comments.add_argument('--limit', type=int, default=100)
    download = commands.add_parser('download', help='通过 HTTP 下载指定问题的附件')
    download.add_argument('key', type=issue_key)
    download.add_argument('attachment_id')
    download.add_argument('--directory', type=Path, required=True)
    search = commands.add_parser('search', help='按 JQL 查询，返回一页结果')
    search.add_argument('jql')
    search.add_argument('--start', type=int, default=0)
    search.add_argument('--limit', type=int, default=100)
    comment = commands.add_parser('comment', help='发送备注；会修改 Jira')
    comment.add_argument('key', type=issue_key)
    comment.add_argument('--body', required=True)
    transition = commands.add_parser('transition', help='执行当前可用的状态流转；会修改 Jira')
    transition.add_argument('key', type=issue_key)
    selector = transition.add_mutually_exclusive_group(required=True)
    selector.add_argument('--id')
    selector.add_argument('--name', help='精确匹配 transitions 中的动作名称')
    transition.add_argument('--fields-file', type=Path, help='可选：状态流转所需 fields 对象的 JSON 文件')
    args = parser.parse_args()
    jira = Jira()
    if args.command == 'me':
        user = jira.request('myself')
        print_json({key: user.get(key) for key in ('name', 'displayName', 'active')})
    elif args.command == 'get':
        print_json(jira.issue(args.key, args.fields))
    elif args.command == 'download':
        print_json(jira.download(args.key, args.attachment_id, args.directory))
    elif args.command == 'comments':
        if args.start < 0 or not 1 <= args.limit <= 100:
            raise JiraError('start 必须非负，limit 范围为 1–100。')
        query = urlencode({'startAt': args.start, 'maxResults': args.limit})
        print_json(jira.request(f'issue/{args.key}/comment?' + query))
    elif args.command == 'transitions':
        print_json(jira.transitions(args.key))
    elif args.command == 'search':
        if args.start < 0 or not 1 <= args.limit <= 100:
            raise JiraError('start 必须非负，limit 范围为 1–100。')
        query = urlencode({'jql': args.jql, 'startAt': args.start, 'maxResults': args.limit,
                           'fields': 'summary,status,resolution,assignee,updated'})
        print_json(jira.request('search?' + query))
    elif args.command == 'comment':
        if not args.body.strip():
            raise JiraError('备注不能为空。')
        result = jira.request(f'issue/{args.key}/comment', {'body': args.body})
        # Read back the specific created comment; never retry POST automatically.
        saved = jira.request(f'issue/{args.key}/comment/{quote(str(result["id"]))}')
        print_json({'key': args.key, 'commentId': saved['id'], 'body': saved['body']})
    elif args.command == 'transition':
        choices = jira.transitions(args.key)
        selected = [item for item in choices if
                    (args.id is not None and item['id'] == args.id) or
                    (args.name is not None and item['name'] == args.name)]
        if len(selected) != 1:
            raise JiraError('动作不存在或名称不唯一，请先查询 transitions 并使用准确 ID。')
        chosen = selected[0]
        fields = json.loads(args.fields_file.read_text()) if args.fields_file else {}
        if not isinstance(fields, dict):
            raise JiraError('fields 文件必须是 JSON 对象。')
        required = [name for name, spec in chosen.get('fields', {}).items()
                    if spec.get('required') and not spec.get('hasDefaultValue') and name not in fields]
        if required:
            raise JiraError('缺少流转必填字段：' + ', '.join(required))
        jira.request(f'issue/{args.key}/transitions', {'transition': {'id': chosen['id']}, 'fields': fields})
        current = jira.issue(args.key)
        actual = current['fields']['status']
        verified = actual['id'] == chosen['to']['id']
        print_json({'key': args.key, 'action': chosen['name'], 'status': actual,
                    'resolution': current['fields']['resolution'], 'verified': verified})
        if not verified:
            raise JiraError('请求已发送，但回读状态与目标不一致；请检查，不自动重发。')


if __name__ == '__main__':
    try:
        main()
    except (JiraError, OSError, ValueError, KeyError) as error:
        print(f'失败：{error}', file=sys.stderr)
        sys.exit(1)
