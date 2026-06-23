#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: run_codex_docker.sh \
  --container-name NAME \
  --image IMAGE \
  --workspace-dir DIR \
  --codex-home-dir DIR \
  --host-codex-home DIR \
  --host-workdir DIR \
  --host-data-source DIR \
  --host-schema-dir DIR \
  --schema-file FILE \
  --prompt PROMPT \
  [--host-artifacts DIR] \
  [--conversation-id ID]
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
      [[ $# -ge 2 ]] || { echo "--container-name requires a value" >&2; usage; exit 2; }
      container_name="$2"
      shift 2
      ;;
    --image)
      [[ $# -ge 2 ]] || { echo "--image requires a value" >&2; usage; exit 2; }
      image="$2"
      shift 2
      ;;
    --workspace-dir)
      [[ $# -ge 2 ]] || { echo "--workspace-dir requires a value" >&2; usage; exit 2; }
      workspace_dir="$2"
      shift 2
      ;;
    --codex-home-dir)
      [[ $# -ge 2 ]] || { echo "--codex-home-dir requires a value" >&2; usage; exit 2; }
      codex_home_dir="$2"
      shift 2
      ;;
    --host-codex-home)
      [[ $# -ge 2 ]] || { echo "--host-codex-home requires a value" >&2; usage; exit 2; }
      host_codex_home="$2"
      shift 2
      ;;
    --host-workdir)
      [[ $# -ge 2 ]] || { echo "--host-workdir requires a value" >&2; usage; exit 2; }
      host_workdir="$2"
      shift 2
      ;;
    --host-data-source)
      [[ $# -ge 2 ]] || { echo "--host-data-source requires a value" >&2; usage; exit 2; }
      host_data_source="$2"
      shift 2
      ;;
    --host-schema-dir)
      [[ $# -ge 2 ]] || { echo "--host-schema-dir requires a value" >&2; usage; exit 2; }
      host_schema_dir="$2"
      shift 2
      ;;
    --schema-file)
      [[ $# -ge 2 ]] || { echo "--schema-file requires a value" >&2; usage; exit 2; }
      schema_file="$2"
      shift 2
      ;;
    --prompt)
      [[ $# -ge 2 ]] || { echo "--prompt requires a value" >&2; usage; exit 2; }
      prompt="$2"
      shift 2
      ;;
    --host-artifacts)
      [[ $# -ge 2 ]] || { echo "--host-artifacts requires a value" >&2; usage; exit 2; }
      host_artifacts="$2"
      shift 2
      ;;
    --conversation-id)
      [[ $# -ge 2 ]] || { echo "--conversation-id requires a value" >&2; usage; exit 2; }
      conversation_id="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

required_values=(
  "$container_name"
  "$image"
  "$workspace_dir"
  "$codex_home_dir"
  "$host_codex_home"
  "$host_workdir"
  "$host_data_source"
  "$host_schema_dir"
  "$schema_file"
  "$prompt"
)
for value in "${required_values[@]}"; do
  if [[ -z "$value" ]]; then
    echo "required argument is missing" >&2
    usage
    exit 2
  fi
done

if [[ "$schema_file" == *"/"* || "$schema_file" == *".."* ]]; then
  echo "--schema-file must be a file name without path traversal" >&2
  exit 2
fi

schema_mount_dir="/tmp/output_json_schema"
docker_args=(
  run
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
  --mount "type=bind,source=$host_schema_dir,target=$schema_mount_dir,readonly"
  --workdir "$workspace_dir"
)

if [[ -n "$host_artifacts" ]]; then
  docker_args+=(--mount "type=bind,source=$host_artifacts,target=$workspace_dir/artifacts,readonly")
fi

codex_args=(
  codex
  exec
  --json
  --skip-git-repo-check
  --sandbox workspace-write
  --cd "$workspace_dir"
  --output-schema "$schema_mount_dir/$schema_file"
)

if [[ -n "$conversation_id" ]]; then
  codex_args+=(resume "$conversation_id" "$prompt")
else
  codex_args+=("$prompt")
fi

exec docker "${docker_args[@]}" "$image" "${codex_args[@]}" < /dev/null
