docker run --rm \
  --user "$(id -u):$(id -g)" \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g \
  --security-opt seccomp=unconfined \
  --cap-drop ALL \
  -e CODEX_API_KEY="$CODEX_API_KEY" \
  -e HOME=/home/codex \
  -e CODEX_HOME=/home/codex/.codex \
  --mount type=bind,source="$PWD/.codex",target=/home/codex/.codex \
  --mount type=bind,source="$PWD/work",target=/workspace \
  --mount type=bind,source="$PWD/data_source",target=/workspace/data_source,readonly \
  --workdir /workspace \
  codex-python-runner:latest \
  codex exec \
    --json \
    --skip-git-repo-check \
    --sandbox workspace-write \
    "$@"