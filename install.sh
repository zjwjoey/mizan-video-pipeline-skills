#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
skill_root="${1:-${CODEX_HOME:-$HOME/.codex}/skills}"
backup_root="$(dirname -- "$skill_root")/skill-backups/$(date +%Y%m%d-%H%M%S)"
skills=(
  video-storyboard-compiler
  gpt-image-ext-material-generation
  dreamina-cli
  capcut-mate-video-pipeline
)

mkdir -p "$skill_root"
for name in "${skills[@]}"; do
  source="$repo_root/skills/$name"
  destination="$skill_root/$name"
  if [[ ! -d "$source" ]]; then
    printf 'Missing packaged skill: %s\n' "$source" >&2
    exit 1
  fi
  if [[ -e "$destination" ]]; then
    mkdir -p "$backup_root"
    mv -- "$destination" "$backup_root/$name"
  fi
  cp -R -- "$source" "$destination"
done

printf 'Installed four pipeline skills under: %s\n' "$skill_root"
if [[ -d "$backup_root" ]]; then
  printf 'Previous versions backed up under: %s\n' "$backup_root"
fi
