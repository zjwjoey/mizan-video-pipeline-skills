#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
skill_root="${1:-${CODEX_HOME:-$HOME/.codex}/skills}"
backup_root="$(dirname -- "$skill_root")/skill-backups/$(date +%Y%m%d-%H%M%S)-$$"
skills=(
  video-storyboard-compiler
  gpt-image-ext-material-generation
  dreamina-canvas-bootstrap
  dreamina-cli
  capcut-mate-video-pipeline
)

for name in "${skills[@]}"; do
  source="$repo_root/skills/$name"
  if [[ ! -d "$source" ]]; then
    printf 'Missing packaged skill: %s\n' "$source" >&2
    exit 1
  fi
done
mkdir -p "$skill_root"
skill_root="$(cd -- "$skill_root" && pwd)"
if [[ "$skill_root" == "$repo_root/skills" ]]; then
  printf 'Installation target must not be the source directory.\n' >&2
  exit 1
fi
for name in "${skills[@]}"; do
  source="$repo_root/skills/$name"
  destination="$skill_root/$name"
  if [[ -e "$destination" ]]; then
    mkdir -p "$backup_root"
    mv -- "$destination" "$backup_root/$name"
  fi
  if ! cp -R -- "$source" "$destination"; then
    mkdir -p "$backup_root"
    [[ ! -e "$destination" ]] || mv -- "$destination" "$backup_root/$name.partial"
    [[ ! -e "$backup_root/$name" ]] || mv -- "$backup_root/$name" "$destination"
    exit 1
  fi
done

printf 'Installed five pipeline skills under: %s\n' "$skill_root"
if [[ -d "$backup_root" ]]; then
  printf 'Previous versions backed up under: %s\n' "$backup_root"
fi
