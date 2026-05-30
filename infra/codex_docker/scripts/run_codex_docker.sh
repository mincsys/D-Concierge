#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: run_codex_docker.sh <prompt>" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
codex_docker_dir="$(cd "$script_dir/.." && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
backend_script="$repo_root/src/backend/infrastructure/codex/run_codex_docker.sh"
prompt="$*"
container_name="d-concierge-manual-$(date +%s)-$$"

mkdir -p \
  "$codex_docker_dir/.codex" \
  "$codex_docker_dir/work/tmp" \
  "$codex_docker_dir/work/artifacts" \
  "$codex_docker_dir/datasource"

CODEX_API_KEY="${CODEX_API_KEY-}" exec "$backend_script" \
  --container-name "$container_name" \
  --image "codex-python-runner:latest" \
  --workspace-dir "/workspace" \
  --codex-home-dir "/home/codex/.codex" \
  --host-codex-home "$codex_docker_dir/.codex" \
  --host-workdir "$codex_docker_dir/work" \
  --host-datasource "$codex_docker_dir/datasource" \
  --host-schema-dir "$repo_root/codex/output_json_schema" \
  --schema-file "pdf-reference-schema.json" \
  --prompt "$prompt"
