# Docker Compose版でCodex実行コンテナを起動できない可能性

## 概要

Codex実行方式をDockerコンテナ実行へ変更したため、Docker Compose版のアプリコンテナからCodex実行コンテナを起動するには、Docker-outside-of-DockerまたはDocker-in-Dockerの構成が必要になる。

現状の `infra/Dockerfile` と `infra/compose.yml` では、Docker Compose版のアプリコンテナ内から `docker run` を実行する前提が満たされていない可能性がある。

## 問題点

- `infra/Dockerfile` のruntimeイメージにDocker CLIが含まれていない。
- `infra/compose.yml` の `app` サービスに `/var/run/docker.sock` がマウントされていない。
- Docker-outside-of-Dockerでは、`docker run --mount source=...` の `source` はアプリコンテナ内パスではなくDockerホスト側パスとして解釈される。
- 現状の設定では、アプリコンテナ内の `/app/codex/...` とDockerホスト側の実パスが一致しないため、Codex実行コンテナへのbind mountが失敗する可能性がある。

## 対応方針

Docker-in-Dockerはprivileged起動や内部Docker daemon管理が必要になるため採用しない。Docker Compose版ではDocker-outside-of-Dockerを採用する。

Docker Compose版では、アプリイメージにDocker CLIを含め、`app` サービスに `/var/run/docker.sock` をマウントする。Docker daemonはアプリコンテナ内に持たず、Dockerホスト側のdaemonを使用する。

パス変換の設定は必要最小限にし、`codex_docker.host_base_dir` を追加する。`host_base_dir` は「Dockerホストから見たアプリ配置ルート」を表す。

例:

```yaml
codex_docker:
  image: "codex-python-runner:latest"
  workspace_dir: "/workspace"
  codex_home_dir: "/home/codex/.codex"
  codex_api_key: ""
  host_base_dir: "/opt/d-concierge"
```

この場合、アプリ内の設定パスは従来どおり利用し、Codex実行コンテナのbind mountに渡す直前だけ、アプリ配置ルートをDockerホスト側の `host_base_dir` へ置き換える。

アプリをDockerなしで直接起動する場合は、`host_base_dir` に空文字を設定する。空文字の場合はパス変換を行わず、アプリから見えるパスをそのまま `docker run --mount source=...` へ渡す。

## 確認が必要な内容

- Docker socketをアプリコンテナへ渡す運用上のリスクを、設計書と環境構築書へ明記するか。
- `host_base_dir` によるパス変換対象を、設定ファイルから解決されたアプリ配置ルート配下のパスに限定するか。
