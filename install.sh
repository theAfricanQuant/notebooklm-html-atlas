#!/usr/bin/env sh
# Copy this dependency-free skill to a local agent skill directory. No downloads occur.
set -eu

usage() {
  echo "Usage: $0 --agent codex|claude | --target /path/to/skill-directory" >&2
  exit 2
}

[ "$#" -eq 2 ] || usage
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$1" in
  --agent)
    case "$2" in
      codex) target="${HOME}/.codex/skills/notebooklm-html-atlas" ;;
      claude) target="${HOME}/.claude/skills/notebooklm-html-atlas" ;;
      *) usage ;;
    esac
    ;;
  --target) target=$2 ;;
  *) usage ;;
esac

mkdir -p "$target/scripts" "$target/references"
cp "$root/SKILL.md" "$target/SKILL.md"
cp "$root/scripts/build_html_report.py" "$target/scripts/build_html_report.py"
cp "$root/scripts/export_notebooklm_atlas.py" "$target/scripts/export_notebooklm_atlas.py"
[ ! -d "$root/references" ] || cp -R "$root/references/." "$target/references/"
printf 'Installed NotebookLM HTML Atlas skill files in %s\n' "$target"
