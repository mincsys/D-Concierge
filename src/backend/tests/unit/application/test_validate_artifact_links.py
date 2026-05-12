from pathlib import Path

from backend.application.artifacts.validate_artifact_links import ArtifactLinkValidator
from backend.application.validation.instruction_messages import (
    get_artifact_link_validation_message,
)


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
    assert result.invalid_targets == ()
    assert result.missing_targets == ()
    assert result.disallowed_suffix_targets == ()


def test_artifact_link_validator_normalizes_backslash_artifact_paths(
    tmp_path: Path,
) -> None:
    """観点：成果物リンク固定検証。

    確認：Codex出力のartifacts配下リンクは区切り文字差分をPOSIX相対形式へ標準化する。
    """
    session_workdir = tmp_path / "session"
    artifacts_dir = session_workdir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "chart.jpg").write_bytes(b"jpg")
    (artifacts_dir / "report.csv").write_text("a,b", encoding="utf-8")

    result = ArtifactLinkValidator().validate(
        markdowns=(
            '![図](artifacts\\chart.jpg)\n<a href=".\\artifacts\\report.csv">CSV</a>',
        ),
        session_workdir=session_workdir,
    )

    assert result.valid is True
    assert result.has_artifact_links is True


def test_artifact_link_validator_rejects_non_artifact_link_targets(
    tmp_path: Path,
) -> None:
    """観点：成果物リンク固定検証。確認：成果物リンクはartifacts配下の相対指定だけ許可する。"""
    result = ArtifactLinkValidator().validate(
        markdowns=(
            "[外部](https://example.test/report.html)\n"
            "![参照元](readonly/chart.png)\n"
            "![絶対](C:\\data\\chart.png)\n"
            "![UNC](\\\\server\\share\\chart.png)\n"
            "![親](artifacts\\..\\secret.png)\n"
            '<img src="/api/artifacts/00000000-0000-0000-0000-000000000001">',
        ),
        session_workdir=tmp_path / "session",
    )

    assert result.valid is False
    assert result.invalid_targets == (
        "https://example.test/report.html",
        "readonly/chart.png",
        "C:\\data\\chart.png",
        "\\\\server\\share\\chart.png",
        "artifacts\\..\\secret.png",
        "/api/artifacts/00000000-0000-0000-0000-000000000001",
    )
    message = get_artifact_link_validation_message(result)
    assert "許可されていない成果物リンク" in message
    assert "- https://example.test/report.html" in message


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
    assert result.missing_targets == ("artifacts/missing.jpeg",)
    assert result.disallowed_suffix_targets == ("artifacts/script.js",)
    message = get_artifact_link_validation_message(result)
    assert "存在しない成果物ファイル" in message
    assert "- artifacts/missing.jpeg" in message
    assert "許可されていない成果物拡張子" in message
    assert "- artifacts/script.js" in message


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
    assert result.disallowed_suffix_targets == ("artifacts/report.html",)
    message = get_artifact_link_validation_message(result)
    assert "許可されていない成果物拡張子" in message
    assert "- artifacts/report.html" in message
