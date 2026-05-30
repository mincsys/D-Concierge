#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: run_codex_docker.sh
  --container-name <name>
  --image <image>
  --workspace-dir <container-path>
  --codex-home-dir <container-path>
  --host-codex-home <host-path>
  --host-workdir <host-path>
  --host-data-source <host-path>
  --host-schema-dir <host-path>
  --schema-file <filename>
  --prompt <prompt>
  [--host-artifacts <host-path>]
  [--conversation-id <conversation-id>]
USAGE
}

container_name=""
image=""
workspace_dir=""
codex_home_dir=""
host_codex_home=""
host_workdir=""
host_data_source=""
host_schema_dir=""
schema_file=""
prompt=""
host_artifacts=""
conversation_id=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --container-name)
      container_name="${2-}"
      shift 2
      ;;
    --image)
      image="${2-}"
      shift 2
      ;;
    --workspace-dir)
      workspace_dir="${2-}"
      shift 2
      ;;
    --codex-home-dir)
      codex_home_dir="${2-}"
      shift 2
      ;;
    --host-codex-home)
      host_codex_home="${2-}"
      shift 2
      ;;
    --host-workdir)
      host_workdir="${2-}"
      shift 2
      ;;
    --host-data-source)
      host_data_source="${2-}"
      shift 2
      ;;
    --host-schema-dir)
      host_schema_dir="${2-}"
      shift 2
      ;;
    --schema-file)
      schema_file="${2-}"
      shift 2
      ;;
    --prompt)
      prompt="${2-}"
      shift 2
      ;;
    --host-artifacts)
      host_artifacts="${2-}"
      shift 2
      ;;
    --conversation-id)
      conversation_id="${2-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

require_value() {
  local name="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    echo "Missing required argument: $name" >&2
    usage
    exit 2
  fi
}

require_value "--container-name" "$container_name"
require_value "--image" "$image"
require_value "--workspace-dir" "$workspace_dir"
require_value "--codex-home-dir" "$codex_home_dir"
require_value "--host-codex-home" "$host_codex_home"
require_value "--host-workdir" "$host_workdir"
require_value "--host-data-source" "$host_data_source"
require_value "--host-schema-dir" "$host_schema_dir"
require_value "--schema-file" "$schema_file"
require_value "--prompt" "$prompt"

if [[ "$schema_file" == *"/"* || "$schema_file" == *".."* ]]; then
  echo "Invalid schema-file: $schema_file" >&2
  exit 2
fi

docker_args=(
  docker run
  --rm
  --name "$container_name"
  --user "$(id -u):$(id -g)"
  --read-only
  --tmpfs /tmp:rw,nosuid,nodev,size=1g
  --security-opt seccomp=unconfined
  --cap-drop ALL
  -e "CODEX_API_KEY=${CODEX_API_KEY-}"
  -e HOME=/home/codex
  -e "CODEX_HOME=$codex_home_dir"
  --mount "type=bind,source=$host_codex_home,target=$codex_home_dir"
  --mount "type=bind,source=$host_workdir,target=$workspace_dir"
  --mount "type=bind,source=$host_data_source,target=$workspace_dir/data_source,readonly"
  --mount "type=bind,source=$host_schema_dir,target=/tmp/output_json_schema,readonly"
  --workdir "$workspace_dir"
)

if [[ -n "$host_artifacts" ]]; then
  docker_args+=(
    --mount "type=bind,source=$host_artifacts,target=$workspace_dir/artifacts,readonly"
  )
fi

codex_args=(
  "$image"
  codex exec
  --json
  --skip-git-repo-check
  --sandbox workspace-write
  --output-schema "/tmp/output_json_schema/$schema_file"
)

if [[ -n "$conversation_id" ]]; then
  codex_args+=(resume "$conversation_id" "$prompt")
else
  codex_args+=("$prompt")
fi

exec "${docker_args[@]}" "${codex_args[@]}"
