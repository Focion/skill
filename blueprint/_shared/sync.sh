#!/usr/bin/env bash
# 把 blueprint/_shared/co-create.md 同步到 blueprint/ 下每个 skill 的 references/。
# co-create.md 是各段共用的共创协议，唯一编辑入口是本目录下的主文件。
# 兼容 macOS 自带的 bash 3.2。

set -euo pipefail

SHARED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
GROUP="$(dirname "$SHARED")"
SRC="$SHARED/co-create.md"
CHECK=0

[ "${1:-}" = "-c" ] && CHECK=1
[ "${1:-}" = "--check" ] && CHECK=1

if [ ! -f "$SRC" ]; then
  echo "缺少主文件：$SRC" >&2
  exit 2
fi

RC=0
for d in "$GROUP"/*/; do
  [ -f "${d}SKILL.md" ] || continue
  dst="${d}references/co-create.md"
  name="$(basename "$d")"
  if [ ! -d "${d}references" ]; then
    echo "跳过 $name：无 references/ 目录" >&2
    RC=1
    continue
  fi
  if [ "$CHECK" = "1" ]; then
    if [ -f "$dst" ] && cmp -s "$SRC" "$dst"; then
      echo "一致  $name"
    else
      echo "不一致 $name"
      RC=1
    fi
  else
    cp "$SRC" "$dst"
    echo "已同步 $name"
  fi
done

exit "$RC"
