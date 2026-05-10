from pathlib import Path

from backend.application.artifacts.validate_artifact_links import ArtifactLinkValidator


def test_artifact_link_validator_accepts_allowed_existing_files(
    tmp_path: Path,
) -> None:
    """観点：成果物リンク固定検証。確認：許可形式、許可拡張子、実ファイル存在を通過する。"""
    session_workdir = tmp_path / "session"
    artifacts_dir = session_workdir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "chart.jpg").write_bytes(b"jpg")
    (artifacts_dir / "report.csv").write_text("a,b", encoding="utf-8")
    (artifacts_dir / "page.html").write_text("<main>ok</main>", encoding="utf-8")

    result = ArtifactLinkValidator().validate(
        markdowns=(
            "![図](./artifacts/chart.jpg)\n"
            "[CSV](artifacts/report.csv)\n"
            '<a href="./artifacts/page.html">HTML</a>',
        ),
        session_workdir=session_workdir,
    )

    assert result.valid is True
    assert result.has_artifact_links is True
    assert result.regeneration_instruction == ""


def test_artifact_link_validator_rejects_non_artifact_link_targets(
    tmp_path: Path,
) -> None:
    """観点：成果物リンク固定検証。確認：成果物リンクはartifacts配下の相対指定だけ許可する。"""
    result = ArtifactLinkValidator().validate(
        markdowns=(
            "[外部](https://example.test/report.html)\n"
            "![参照元](readonly/chart.png)\n"
            '<img src="/api/artifacts/00000000-0000-0000-0000-000000000001">',
        ),
        session_workdir=tmp_path / "session",
    )

    assert result.valid is False
    assert "許可されていない成果物リンク" in result.regeneration_instruction
    assert "- https://example.test/report.html" in result.regeneration_instruction
    assert "- readonly/chart.png" in result.regeneration_instruction
    assert "- /api/artifacts/00000000-0000-0000-0000-000000000001" in (
        result.regeneration_instruction
    )


def test_artifact_link_validator_rejects_missing_and_disallowed_extensions(
    tmp_path: Path,
) -> None:
    """観点：成果物リンク固定検証。確認：存在しないファイルと許可外拡張子を具体的に指摘する。"""
    session_workdir = tmp_path / "session"
    artifacts_dir = session_workdir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "script.js").write_text("alert(1)", encoding="utf-8")

    result = ArtifactLinkValidator().validate(
        markdowns=("![不足](artifacts/missing.jpeg)\n[JS](artifacts/script.js)",),
        session_workdir=session_workdir,
    )

    assert result.valid is False
    assert "存在しない成果物ファイル" in result.regeneration_instruction
    assert "- artifacts/missing.jpeg" in result.regeneration_instruction
    assert "許可されていない成果物拡張子" in result.regeneration_instruction
    assert "- artifacts/script.js" in result.regeneration_instruction


def test_artifact_link_validator_rejects_image_link_to_html(
    tmp_path: Path,
) -> None:
    """観点：成果物リンク固定検証。確認：画像埋め込みでは画像拡張子だけ許可する。"""
    session_workdir = tmp_path / "session"
    artifacts_dir = session_workdir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "report.html").write_text("<main>ok</main>", encoding="utf-8")

    result = ArtifactLinkValidator().validate(
        markdowns=("![HTML](artifacts/report.html)",),
        session_workdir=session_workdir,
    )

    assert result.valid is False
    assert "許可されていない成果物拡張子" in result.regeneration_instruction
    assert "- artifacts/report.html" in result.regeneration_instruction
