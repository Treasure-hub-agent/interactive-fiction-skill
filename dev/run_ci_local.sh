#!/usr/bin/env bash
# run_ci_local.sh — 本地复现 CI 全部步骤（dev 侧，不进发布包、不进 MANIFEST）
#
# 为什么需要它：本机 docker 守护进程未启用（act 依赖容器运行时），
# 因此用本脚本在宿主机上逐步执行与 .github/workflows/ci.yml **完全相同的命令**，
# 作为「CI 会在远端跑通」的本地等价证据；workflow 语法用 actionlint 静态校验。
#
# 用法：bash dev/run_ci_local.sh            # 缺工具=失败（默认，保证证据可信）
#       bash dev/run_ci_local.sh --lenient  # 缺工具=警告跳过（仅本地快速自查用）
#
# ⚠️ 缺工具策略：默认 **strict**——工具缺失即判失败。理由是「跳过后仍报通过」会让
#    等价性证据失真（曾实测：屏蔽工具后脚本照样打印「全部通过」且 exit 0）。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${IFS_DEV_VENV:-$HOME/.local/venvs/ifs-dev}"
cd "$ROOT"

LENIENT=0
for a in "$@"; do [ "$a" = "--lenient" ] && LENIENT=1; done

FAIL=0
step() { printf '\n\033[1m=== %s ===\033[0m\n' "$1"; }
ok()   { printf '  ✅ %s\n' "$1"; }
bad()  { printf '  ❌ %s\n' "$1"; FAIL=1; }

# 缺工具处理：strict 下判失败；--lenient 下仅警告
missing() {
  if [ "$LENIENT" -eq 1 ]; then
    printf '  ⚠️  %s 未安装，已跳过（--lenient 模式，证据不完整）：%s\n' "$1" "$2"
  else
    bad "$1 未安装：$2（如需临时跳过请加 --lenient，但此时结果不作为 CI 等价证据）"
  fi
}

# 工具解析：优先独立 dev venv，回落到 PATH
pick() { if [ -x "$VENV/bin/$1" ]; then echo "$VENV/bin/$1"; else command -v "$1" || true; fi; }
RUFF="$(pick ruff)"; ACTIONLINT="$(pick actionlint)"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"

step "0. workflow 语法静态校验（actionlint）"
if [ -n "$ACTIONLINT" ]; then
  if "$ACTIONLINT" .github/workflows/ci.yml; then ok "actionlint 通过"; else bad "actionlint 报错"; fi
else
  missing "actionlint" "放入 ~/.local/bin"
fi

step "1. 工程门禁 validate.py（六类）"
if python3 scripts/validate.py; then ok "validate 全绿"; else bad "validate 失败"; fi

step "2. 单元测试（既有，scripts/）"
if python3 -m unittest discover -s scripts -p "test_*.py"; then ok "既有单测通过"; else bad "既有单测失败"; fi

step "3. ruff（仅 F/E9 真缺陷规则）"
if [ -n "$RUFF" ]; then
  # 作用域与 CI 保持一致：整个仓库（含 dev/、tests/），规则由 ruff.toml 决定
  if "$RUFF" check . --config ruff.toml; then ok "ruff 无真缺陷"; else bad "ruff 报真缺陷"; fi
else
  missing "ruff" "pip install ruff（或放入 $VENV）"
fi

step "4. 属性测试（Hypothesis，dev 侧 tests/）"
if [ -d tests ]; then
  # 属性测试需 hypothesis（第三方），必须用装有依赖的 dev venv 解释器
  if "$PY" -c "import hypothesis" 2>/dev/null; then
    if "$PY" -m unittest discover -s tests -p "test_*.py"; then ok "属性测试通过"; else bad "属性测试失败"; fi
  else
    missing "hypothesis" "pip install hypothesis（需 Python ≥3.11）"
  fi
else
  bad "tests/ 目录不存在"
fi

step "5. dev 侧工具自测（版本同步边界 + 评测断言正反例）"
if [ -d dev ] && [ -d dev/promptfoo ]; then
  if python3 -m unittest discover -s dev -p "test_*.py" && \
     python3 -m unittest discover -s dev/promptfoo -p "test_*.py"; then
    ok "dev 工具自测通过"
  else
    bad "dev 工具自测失败"
  fi
else
  bad "dev/ 目录不完整（应含 dev/promptfoo/）"
fi

step "6. 发布包边界检查（npm pack 实际内容）"
if [ -f dev/check_pack.py ]; then
  if command -v npm >/dev/null 2>&1; then
    if python3 dev/check_pack.py; then ok "发布包边界通过（无缓存/dev 文件/泄露）"; else bad "发布包边界不合格"; fi
  else
    missing "npm" "安装 Node.js 以验证发布包边界"
  fi
else
  missing "dev/check_pack.py" "发布包边界检查脚本缺失"
fi

printf '\n'
if [ "$FAIL" -eq 0 ]; then
  if [ "$LENIENT" -eq 1 ]; then
    printf '\033[1m✅ 本地检查全部通过（⚠️ --lenient 模式：缺工具项已跳过，不作为 CI 等价证据）\033[0m\n'
  else
    printf '\033[1m✅ 本地 CI 等价验证全部通过\033[0m\n'
  fi
else
  printf '\033[1m❌ 本地 CI 等价验证存在失败项\033[0m\n'
fi
exit "$FAIL"
