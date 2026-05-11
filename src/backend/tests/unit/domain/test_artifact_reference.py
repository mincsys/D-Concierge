from uuid import UUID

import pytest

from backend.domain.artifacts.artifact_reference import (
    ArtifactReference,
    InvalidArtifactReferenceError,
)


def test_artifact_reference_keeps_saved_artifact_metadata() -> None:
    """観点：成果物参照値。確認：保存済み成果物のID、MIME、相対pathを保持する。"""
    artifact = ArtifactReference(
        artifact_id=UUID("00000000-0000-0000-0000-000000000001"),
        mime_type="image/svg+xml",
        relative_path="run-1/chart.svg",
    )

    assert str(artifact.artifact_id) == "00000000-0000-0000-0000-000000000001"
    assert artifact.mime_type == "image/svg+xml"
    assert artifact.relative_path == "run-1/chart.svg"


def test_artifact_reference_rejects_invalid_metadata() -> None:
    """観点：成果物参照値。確認：空MIME、絶対path、親参照を拒否する。"""
    artifact_id = UUID("00000000-0000-0000-0000-000000000001")
    invalid_values = [
        ("", "run-1/chart.svg"),
        ("image/svg+xml", "/run-1/chart.svg"),
        ("image/svg+xml", "../chart.svg"),
        ("image/svg+xml", "run-1\\chart.svg"),
    ]

    for mime_type, relative_path in invalid_values:
        with pytest.raises(InvalidArtifactReferenceError):
            ArtifactReference(
                artifact_id=artifact_id,
                mime_type=mime_type,
                relative_path=relative_path,
            )
