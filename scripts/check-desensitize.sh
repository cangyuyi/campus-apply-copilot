#!/usr/bin/env bash
# 提交前的硬性脱敏检查。有任何命中都不许提交。
# 用法：bash scripts/check-desensitize.sh [目录，默认当前目录]
set -uo pipefail

DIR="${1:-.}"
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

echo "=== 脱敏检查：$DIR ==="
check "手机号"        '1[3-9][0-9]{9}'                                                  '13800000000|13900000000|1\[3-9\]'
check "身份证号"      '[0-9]{17}[0-9Xx]'                                                '3301xxxxxxxxxxxxxx|\[0-9\]\{17\}'
check "邮箱"          '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'                  'example\.com|@[a-zA-Z0-9.-]+\\\\\.[a-zA-Z]'
check "本地绝对路径"  '(/Users/[a-zA-Z0-9_.-]+|/home/[a-zA-Z0-9_.-]+|C:\\\\Users\\\\)' 'path/to|/absolute/path'
check "仓库占位符"    'github\.com/<[a-zA-Z]+>|github\.com/your'                        '<you>|<你的用户名>'

echo
if [ "$FAIL" -eq 0 ]; then
  echo "全部通过，可以提交。"
else
  echo "⚠️  存在命中项，请逐条确认为误报或脱敏后再提交。"
  exit 1
fi
