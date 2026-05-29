docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g \
  --tmpfs /workspace:rw,nosuid,nodev \
  --security-opt seccomp=unconfined \
  --cap-drop ALL \
  -e HOME=/home/codex \
  -e CODEX_HOME=/home/codex/.codex \
  --mount type=bind,source="$PWD/.codex",target=/home/codex/.codex \
  --mount type=bind,source="$PWD/datasource",target=/workspace/readonly,readonly \
  --mount type=bind,source="$PWD/artifacts",target=/workspace/artifacts \
  --workdir /workspace \
  codex-python-runner:latest