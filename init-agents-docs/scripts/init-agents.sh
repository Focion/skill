#!/usr/bin/env bash
# 初始化项目 .agents 文档结构。幂等：已存在的文件默认跳过。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="$SCRIPT_DIR/../assets"

FORCE=0
DRY_RUN=0
TARGET=""

usage() {
  cat <<'EOF'
用法: init-agents.sh [目标目录] [选项]

在目标目录（默认当前目录）下创建 .agents 文档结构。

选项:
  --force     覆盖已存在的 README.md / AGENTS.md（会丢失本地修改）
  --dry-run   只打印将要执行的操作，不写入
  -h, --help  显示本帮助
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --force)   FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    -*)        echo "未知选项: $1" >&2; usage >&2; exit 2 ;;
    *)
      if [ -n "$TARGET" ]; then
        echo "只能指定一个目标目录（已有: $TARGET，又给了: $1）" >&2
        exit 2
      fi
      TARGET="$1"
      ;;
  esac
  shift
done

TARGET="${TARGET:-.}"

if [ ! -d "$TARGET" ]; then
  echo "目标目录不存在: $TARGET" >&2
  exit 1
fi
if [ ! -d "$ASSETS_DIR" ]; then
  echo "模板目录缺失: $ASSETS_DIR" >&2
  exit 1
fi

ROOT="$(cd "$TARGET" && pwd)/.agents"

NOTES_DIRS="research product tech review changelog plan archive"

created=0
skipped=0
overwritten=0

log() { printf '%s\n' "$1"; }

ensure_dir() {
  local dir="$1" rel
  if [ "$dir" = "$ROOT" ]; then
    rel=".agents"
  else
    rel=".agents/${dir#"$ROOT"/}"
  fi
  if [ -d "$dir" ]; then
    log "  skip  $rel/"
    skipped=$((skipped + 1))
  else
    log "  mkdir $rel/"
    created=$((created + 1))
    [ "$DRY_RUN" -eq 1 ] || mkdir -p "$dir"
  fi
}

# ensure_file <模板路径> <目标路径>
ensure_file() {
  local src="$1" dest="$2" rel=".agents/${2#"$ROOT"/}"
  if [ ! -f "$src" ]; then
    echo "模板文件缺失: $src" >&2
    exit 1
  fi
  if [ -f "$dest" ] && [ "$FORCE" -eq 0 ]; then
    log "  skip  $rel (已存在)"
    skipped=$((skipped + 1))
    return
  fi
  if [ -f "$dest" ]; then
    log "  FORCE $rel (覆盖)"
    overwritten=$((overwritten + 1))
  else
    log "  write $rel"
    created=$((created + 1))
  fi
  [ "$DRY_RUN" -eq 1 ] || cp "$src" "$dest"
}

[ "$DRY_RUN" -eq 1 ] && log "== dry-run，不会写入任何文件 =="
log "目标: $ROOT"
log ""

ensure_dir "$ROOT"
ensure_file "$ASSETS_DIR/AGENTS.md" "$ROOT/AGENTS.md"

ensure_dir "$ROOT/notes"
for d in $NOTES_DIRS; do
  ensure_dir "$ROOT/notes/$d"
  ensure_file "$ASSETS_DIR/notes/$d.md" "$ROOT/notes/$d/README.md"
done

ensure_dir "$ROOT/skills"
ensure_file "$ASSETS_DIR/skills/README.md" "$ROOT/skills/README.md"

log ""
log "完成：新建 $created，跳过 $skipped，覆盖 $overwritten"

if [ "$DRY_RUN" -eq 0 ]; then
  log ""
  if command -v tree >/dev/null 2>&1; then
    tree -a --noreport "$ROOT"
  else
    find "$ROOT" -print | sed -e "s|^$(dirname "$ROOT")/||" -e 's|[^/]*/|  |g'
  fi
fi

log ""
log "下一步：编辑 $ROOT/AGENTS.md 的「项目上下文」一节，替换为本项目真实信息。"
