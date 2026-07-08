#!/usr/bin/env bash
# VPN 网络诊断脚本 — 快速判断是 TCP/UDP 还是线路问题
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SERVER="122.248.253.52"
TIMEOUT=10

pass()  { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; }
header() { echo -e "\n${GREEN}──${NC} $1 ${GREEN}──${NC}"; }

# ── 1. 协议检测 ──────────────────────────────────────────
header "1. 当前隧道协议"

proto=$(netstat -an 2>/dev/null | grep "$SERVER" | head -1 || true)
if echo "$proto" | grep -q 'tcp'; then
    fail "当前走 TCP（这是慢的根因！）"
    echo "   $proto"
elif echo "$proto" | grep -q 'udp'; then
    pass "当前走 UDP（正确）"
else
    warn "未检测到与 $SERVER 的连接，VPN 可能未连接"
fi

# ── 2. DNS 解析速度 ─────────────────────────────────────
header "2. DNS 解析"

dns_result=$(dig +short google.com @1.1.1.1 2>/dev/null | head -1)
if [ -n "$dns_result" ]; then
    dns_time=$( { time dig +short google.com @1.1.1.1 > /dev/null; } 2>&1 | awk '/real/{print $2}')
    pass "解析到 $dns_result (${dns_time})"
else
    fail "DNS 解析失败"
fi

# ── 3. 到 Google 的延迟 ──────────────────────────────────
header "3. Google 延迟（应 < 300ms）"

if has_ping=$(ping -c 3 -W 3 google.com 2>&1); then
    avg=$(echo "$has_ping" | tail -1 | awk -F'/' '{print $5}')
    if [ -n "$avg" ]; then
        avg_int=${avg%.*}
        if [ "$avg_int" -lt 300 ]; then
            pass "RTT 平均 ${avg}ms — 正常"
        elif [ "$avg_int" -lt 800 ]; then
            warn "RTT 平均 ${avg}ms — 偏慢"
        else
            fail "RTT 平均 ${avg}ms — 极慢，大概率是 TCP 或线路拥塞"
        fi
    fi
else
    fail "ping 不通 Google，隧道可能已死"
fi

# ── 4. HTTP 访问 Google ──────────────────────────────────
header "4. HTTPS 访问 google.com（应 < 3s）"

http_result=$(curl -o /dev/null -s -w "connect:%{time_connect} ttfb:%{time_starttransfer} total:%{time_total} http:%{http_code}" \
    --noproxy '*' --max-time "$TIMEOUT" https://www.google.com 2>&1 || echo "timeout")

_parse() { echo "$http_result" | awk -F"$1:" '{print $2}' | awk '{print $1}'; }
connect=$(_parse connect)
ttfb=$(_parse ttfb)
total=$(_parse total)
http_code=$(_parse http)
[ -z "$connect" ] && connect=0
[ -z "$ttfb" ] && ttfb=0
[ -z "$total" ] && total=0
[ -z "$http_code" ] && http_code=000

_lt() { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a < b) }'; }

if [ "$http_code" = "200" ]; then
    if _lt "$total" 3; then
        pass "HTTP 200, 总耗时 ${total}s — 正常"
    elif _lt "$total" 8; then
        warn "HTTP 200, 总耗时 ${total}s — 偏慢（connect:${connect}s TTFB:${ttfb}s）"
    else
        fail "HTTP 200, 总耗时 ${total}s — 极慢（connect:${connect}s TTFB:${ttfb}s）"
    fi
else
    fail "HTTP ${http_code}, 无法访问 Google"
    echo "   原始输出: $http_result"
fi

# ── 5. 总结 ──────────────────────────────────────────────
header "5. 诊断结论"

if echo "$proto" | grep -q 'tcp'; then
    fail "TCP 模式是速度慢的根因。修复方法："
    echo "   cd ~/.codex/repos/destiny-skill && git pull"
    echo "   然后 voff && vpn 重连即可"
elif [ "$http_code" = "200" ]; then
    if _lt "$total" 3; then
        pass "一切正常，无需处理"
    elif _lt "$total" 8; then
        warn "速度偏慢但不是 TCP 问题，可能是晚高峰线路拥塞，稍后再试"
    else
        fail "速度严重异常，检查 VPN 服务器是否正常、是否到了晚高峰"
    fi
else
    fail "VPN 隧道不通，先运行 voff 然后 vpn 重新连接"
fi

echo ""
