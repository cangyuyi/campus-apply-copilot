#!/usr/bin/env bash
# 提交前的硬性脱敏检查。有任何命中都不许提交。
# 用法：bash scripts/check-desensitize.sh [目录，默认当前目录]
#
# 两类规则：
#   1) 通用规则：手机号 / 身份证 / 邮箱 / 本地路径 / candidateId 假号段
#   2) 本地私密黑名单：真实项目名、公司名、部门名等
#      放在 scripts/desensitize-blocklist.local.txt（已被 .gitignore 忽略），
#      一行一个词。这样"要保护的名字"不会反过来被写进公开脚本。
set -uo pipefail

DIR="${1:-.}"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLOCKLIST="${DESENSITIZE_BLOCKLIST:-$SELF_DIR/desensitize-blocklist.local.txt}"
FAIL=0

check() {
  local label="$1" pattern="$2" exclude="${3:-}"
  local out
  if [ -n "$exclude" ]; then
    out=$(grep -rnE "$pattern" "$DIR" --include='*.md' --include='*.json' --include='*.csv' --include='*.py' --include='*.sh' 2>/dev/null | grep -vE "$exclude")
  else
    out=$(grep -rnE "$pattern" "$DIR" --include='*.md' --include='*.json' --include='*.csv' --include='*.py' --include='*.sh' 2>/dev/null)
  fi
  if [ -n "$out" ]; then
    echo "✗ $label"
    echo "$out" | sed 's/^/    /'
    FAIL=1
  else
    echo "✓ $label"
  fi
}

# 黑名单用固定字符串匹配，避免真实名字里的 . ( ) 等被当成正则
check_fixed() {
  local label="$1" term="$2"
  local out
  out=$(grep -rnF "$term" "$DIR" --include='*.md' --include='*.json' --include='*.csv' --include='*.py' --include='*.sh' 2>/dev/null)
  if [ -n "$out" ]; then
    echo "✗ $label"
    echo "$out" | sed 's/^/    /'
    FAIL=1
  else
    echo "✓ $label"
  fi
}

echo "=== 脱敏检查：$DIR ==="

# ── 通用规则 ──
check "手机号"        '1[3-9][0-9]{9}'                                                  '13800000000|13900000000|1\[3-9\]'
check "身份证号"      '[0-9]{17}[0-9Xx]'                                                '3301xxxxxxxxxxxxxx|\[0-9\]\{17\}'
check "邮箱"          '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'                  'example\.com|@[a-zA-Z0-9.-]+\\\\\.[a-zA-Z]'
check "本地绝对路径"  '(/Users/[a-zA-Z0-9_.-]+|/home/[a-zA-Z0-9_.-]+|C:\\\\Users\\\\)' 'path/to|/absolute/path'
check "仓库占位符"    'github\.com/<[a-zA-Z]+>|github\.com/your'                        '<you>|<你的用户名>'

# candidateId / jobId 一律使用文档约定的 8000000xx 假号段；
# 出现任何其它 6 位以上的编号即视为真实投递 ID 泄漏。
check "非假号段的 candidateId/jobId" \
  '(candidateId|jobId)=[0-9]{6,}' \
  '(candidateId|jobId)=8000000[0-9]{2}'

# ── 本地私密黑名单 ──
echo
if [ -f "$BLOCKLIST" ]; then
  echo "（已加载本地黑名单：$(basename "$BLOCKLIST")）"
  count=0
  while IFS= read -r term || [ -n "$term" ]; do
    term="$(printf '%s' "$term" | sed 's/[[:space:]]*$//')"
    [ -z "$term" ] && continue
    case "$term" in \#*) continue ;; esac
    count=$((count + 1))
    check_fixed "本地黑名单：$term" "$term"
  done < "$BLOCKLIST"
  if [ "$count" -eq 0 ]; then
    echo "  （黑名单为空，未启用词条检查）"
  fi
else
  echo "⚠️  未找到本地黑名单：$BLOCKLIST"
  echo "    建议复制 scripts/desensitize-blocklist.example.txt 为该文件，"
  echo "    填入你真实的项目名 / 公司名 / 部门名 / 投递系统名，"
  echo "    之后每次提交都会被自动拦住。该文件已被 .gitignore 忽略，不会上传。"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "全部通过，可以提交。"
else
  echo "⚠️  存在命中项，请逐条确认为误报或脱敏后再提交。"
  exit 1
fi
