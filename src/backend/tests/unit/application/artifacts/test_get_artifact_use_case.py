from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from backend.application.ports.database.dto import ArtifactData
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.chat import F003_USER_ID, OTHER_USER_ID

if TYPE_CHECKING:
    from backend.application.ports.filesystem.dto import OpenedArtifactFile

ARTIFACT_ID_VALUE = UUID("bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb")
TRACE_ID_VALUE = "018fe2d4-0000-7000-8000-000000000006"


@dataclass(slots=True)
class FakeArtifactDeliveryRepository:
    artifacts: dict[tuple[str, UUID], ArtifactData | None]
    errors: dict[tuple[str, UUID], AppError] = field(default_factory=dict)
    requested: list[tuple[str, UUID]] = field(default_factory=list)

    def get_artifact_for_delivery(
        self,
        user_id: str,
        artifact_id: UUID,
    ) -> ArtifactData | None:
        self.requested.append((user_id, artifact_id))
        error = self.errors.get((user_id, artifact_id))
        if error is not None:
            raise error
        return self.artifacts.get((user_id, artifact_id))


@dataclass(slots=True)
class FakeArtifactStore:
    file_path: Path
    error: AppError | None = None
    opened_artifacts: list[ArtifactData] = field(default_factory=list)

    def open_saved_file(self, artifact: ArtifactData) -> OpenedArtifactFile:
        from backend.application.ports.filesystem.dto import OpenedArtifactFile

        self.opened_artifacts.append(artifact)
        if self.error is not None:
            raise self.error
        return OpenedArtifactFile(
            file_path=self.file_path,
            mime_type=artifact.mime_type,
        )


def test_get_artifact_returns_saved_file_with_persisted_mime_type(
    tmp_path: Path,
) -> None:
    """
    観点：GetArtifactUseCaseが保存済み成果物メタとファイル境界を結合すること
    確認：認証ユーザの成果物IDから保存済みstorage_pathを開き、
    保存時MIMEタイプと配信用ファイルパスを返すこと
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    artifact = _artifact_data(
        storage_path=f"{F003_USER_ID}/session/{ARTIFACT_ID_VALUE}.svg",
        mime_type="image/svg+xml",
    )
    repository = FakeArtifactDeliveryRepository(
        artifacts={(F003_USER_ID, ARTIFACT_ID_VALUE): artifact},
    )
    store = FakeArtifactStore(file_path=tmp_path / "saved.svg")
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    result = use_case.execute(
        GetArtifactCommand(
            user_id=F003_USER_ID,
            artifact_id=ARTIFACT_ID_VALUE,
            trace_id=TRACE_ID_VALUE,
        ),
    )

    assert repository.requested == [(F003_USER_ID, ARTIFACT_ID_VALUE)]
    assert store.opened_artifacts == [artifact]
    assert result.file_path == tmp_path / "saved.svg"
    assert result.mime_type == "image/svg+xml"


def test_get_artifact_rejects_missing_artifact_without_file_access(
    tmp_path: Path,
) -> None:
    """
    観点：GetArtifactUseCaseが未採用または他ユーザの成果物を配信しないこと
    確認：成果物IDが認証ユーザの採用済み回答に紐づかない場合はNOT_FOUNDとなり、
    ArtifactStoreを呼び出さないこと
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    repository = FakeArtifactDeliveryRepository(
        artifacts={(F003_USER_ID, ARTIFACT_ID_VALUE): None},
    )
    store = FakeArtifactStore(file_path=tmp_path / "saved.svg")
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetArtifactCommand(
                user_id=F003_USER_ID,
                artifact_id=ARTIFACT_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.NOT_FOUND
    assert raised.value.trace is False
    assert store.opened_artifacts == []


def test_get_artifact_rejects_other_user_artifact_without_file_access(
    tmp_path: Path,
) -> None:
    """
    観点：GetArtifactUseCaseが認証ユーザ所有外の成果物を配信しないこと
    確認：別ユーザに紐づく同一成果物IDはNOT_FOUNDとなり、
    ArtifactStoreを呼び出さないこと
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    artifact = _artifact_data(
        storage_path=f"{OTHER_USER_ID}/session/{ARTIFACT_ID_VALUE}.svg",
        mime_type="image/svg+xml",
    )
    repository = FakeArtifactDeliveryRepository(
        artifacts={(OTHER_USER_ID, ARTIFACT_ID_VALUE): artifact},
    )
    store = FakeArtifactStore(file_path=tmp_path / "saved.svg")
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetArtifactCommand(
                user_id=F003_USER_ID,
                artifact_id=ARTIFACT_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.NOT_FOUND
    assert store.opened_artifacts == []


def test_get_artifact_rejects_deleting_chat_without_file_access(
    tmp_path: Path,
) -> None:
    """
    観点：GetArtifactUseCaseが削除中チャットに紐づく成果物を配信しないこと
    確認：Repository境界のCONFLICTを返し、保存済み成果物ファイルを開かないこと
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    repository = FakeArtifactDeliveryRepository(
        artifacts={},
        errors={
            (F003_USER_ID, ARTIFACT_ID_VALUE): AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            ),
        },
    )
    store = FakeArtifactStore(file_path=tmp_path / "saved.svg")
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetArtifactCommand(
                user_id=F003_USER_ID,
                artifact_id=ARTIFACT_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.CONFLICT
    assert raised.value.trace is False
    assert store.opened_artifacts == []


def test_get_artifact_rejects_disallowed_mime_type_without_file_access(
    tmp_path: Path,
) -> None:
    """
    観点：GetArtifactUseCaseが配信可能なMIMEタイプを保存済みメタ情報で制限すること
    確認：許可外MIMEタイプの成果物はFORBIDDENとなり、
    保存済みファイル実体を開かないこと
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    artifact = _artifact_data(
        storage_path=f"{F003_USER_ID}/session/{ARTIFACT_ID_VALUE}.bin",
        mime_type="application/octet-stream",
    )
    repository = FakeArtifactDeliveryRepository(
        artifacts={(F003_USER_ID, ARTIFACT_ID_VALUE): artifact},
    )
    store = FakeArtifactStore(file_path=tmp_path / "saved.bin")
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetArtifactCommand(
                user_id=F003_USER_ID,
                artifact_id=ARTIFACT_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.FORBIDDEN
    assert store.opened_artifacts == []


def test_get_artifact_rejects_mime_extension_mismatch_without_file_access(
    tmp_path: Path,
) -> None:
    """
    観点：GetArtifactUseCaseが保存済みMIMEタイプとstorage_path拡張子の整合を検証すること
    確認：.svgにtext/htmlなどの不一致はFORBIDDENとなり、保存済みファイルを開かないこと
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    artifact = _artifact_data(
        storage_path=f"{F003_USER_ID}/session/{ARTIFACT_ID_VALUE}.svg",
        mime_type="text/html",
    )
    repository = FakeArtifactDeliveryRepository(
        artifacts={(F003_USER_ID, ARTIFACT_ID_VALUE): artifact},
    )
    store = FakeArtifactStore(file_path=tmp_path / "saved.svg")
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetArtifactCommand(
                user_id=F003_USER_ID,
                artifact_id=ARTIFACT_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.FORBIDDEN
    assert raised.value.trace is False
    assert store.opened_artifacts == []


@pytest.mark.parametrize(
    ("extension", "mime_type"),
    [
        ("html", "text/html"),
        ("csv", "text/csv"),
    ],
)
def test_get_artifact_returns_allowed_text_artifacts_with_persisted_mime_type(
    tmp_path: Path,
    extension: str,
    mime_type: str,
) -> None:
    """
    観点：GetArtifactUseCaseが非画像の許可MIMEタイプを配信対象に含めること
    確認：text/htmlとtext/csvの保存済み成果物を同じMIMEタイプで返すこと
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    artifact = _artifact_data(
        storage_path=f"{F003_USER_ID}/session/{ARTIFACT_ID_VALUE}.{extension}",
        mime_type=mime_type,
    )
    repository = FakeArtifactDeliveryRepository(
        artifacts={(F003_USER_ID, ARTIFACT_ID_VALUE): artifact},
    )
    store = FakeArtifactStore(file_path=tmp_path / f"saved.{extension}")
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    result = use_case.execute(
        GetArtifactCommand(
            user_id=F003_USER_ID,
            artifact_id=ARTIFACT_ID_VALUE,
            trace_id=TRACE_ID_VALUE,
        ),
    )

    assert store.opened_artifacts == [artifact]
    assert result.file_path == tmp_path / f"saved.{extension}"
    assert result.mime_type == mime_type


def test_get_artifact_returns_store_missing_file_as_not_found(tmp_path: Path) -> None:
    """
    観点：GetArtifactUseCaseが成果物メタ存在時の実ファイル欠損を扱うこと
    確認：ArtifactStoreのNOT_FOUNDを返し、対象成果物だけを開こうとすること
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    artifact = _artifact_data(
        storage_path=f"{F003_USER_ID}/session/{ARTIFACT_ID_VALUE}.svg",
        mime_type="image/svg+xml",
    )
    repository = FakeArtifactDeliveryRepository(
        artifacts={(F003_USER_ID, ARTIFACT_ID_VALUE): artifact},
    )
    store = FakeArtifactStore(
        file_path=tmp_path / "missing.svg",
        error=AppError(
            error_type=ErrorType.NOT_FOUND,
            trace=True,
            diagnostic_message="保存済み成果物が見つかりません。",
        ),
    )
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetArtifactCommand(
                user_id=F003_USER_ID,
                artifact_id=ARTIFACT_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.NOT_FOUND
    assert raised.value.trace is True
    assert store.opened_artifacts == [artifact]


def test_get_artifact_returns_store_read_failure_as_system(tmp_path: Path) -> None:
    """
    観点：GetArtifactUseCaseが成果物メタ存在時のファイル読込失敗を扱うこと
    確認：ArtifactStoreのSYSTEMを返し、対象成果物だけを開こうとすること
    """
    from backend.application.artifacts.get_artifact import (
        GetArtifactCommand,
        GetArtifactUseCase,
    )

    artifact = _artifact_data(
        storage_path=f"{F003_USER_ID}/session/{ARTIFACT_ID_VALUE}.svg",
        mime_type="image/svg+xml",
    )
    repository = FakeArtifactDeliveryRepository(
        artifacts={(F003_USER_ID, ARTIFACT_ID_VALUE): artifact},
    )
    store = FakeArtifactStore(
        file_path=tmp_path / "broken.svg",
        error=AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="保存済み成果物を読み込めません。",
        ),
    )
    use_case = GetArtifactUseCase(repository=repository, artifact_store=store)

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetArtifactCommand(
                user_id=F003_USER_ID,
                artifact_id=ARTIFACT_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert store.opened_artifacts == [artifact]


def _artifact_data(
    *,
    storage_path: str,
    mime_type: str,
) -> ArtifactData:
    return ArtifactData(
        artifact_id=ARTIFACT_ID_VALUE,
        mime_type=mime_type,
        storage_path=storage_path,
        created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
