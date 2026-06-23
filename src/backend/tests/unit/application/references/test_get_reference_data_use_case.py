from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from backend.application.ports.database.dto import DisplayReferenceData
from backend.shared.errors.error_type import ErrorType
from backend.shared.errors.errors import AppError
from backend.tests.support.chat import F003_USER_ID, OTHER_USER_ID

if TYPE_CHECKING:
    from backend.application.ports.filesystem.dto import OpenedReferenceFile

REFERENCE_ID_VALUE = UUID("aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa")
TRACE_ID_VALUE = "018fe2d4-0000-7000-8000-000000000006"


@dataclass(slots=True)
class FakeReferenceDeliveryRepository:
    references: dict[tuple[str, UUID], DisplayReferenceData | None]
    errors: dict[tuple[str, UUID], AppError] = field(default_factory=dict)
    requested: list[tuple[str, UUID]] = field(default_factory=list)

    def get_reference_for_delivery(
        self,
        user_id: str,
        reference_id: UUID,
    ) -> DisplayReferenceData | None:
        self.requested.append((user_id, reference_id))
        error = self.errors.get((user_id, reference_id))
        if error is not None:
            raise error
        return self.references.get((user_id, reference_id))


@dataclass(slots=True)
class FakeReferenceStore:
    file_path: Path
    mime_type: str = "application/pdf"
    error: AppError | None = None
    opened_paths: list[str] = field(default_factory=list)

    def open_reference_file(self, relative_path: str) -> OpenedReferenceFile:
        from backend.application.ports.filesystem.dto import OpenedReferenceFile

        self.opened_paths.append(relative_path)
        if self.error is not None:
            raise self.error
        return OpenedReferenceFile(file_path=self.file_path, mime_type=self.mime_type)


def test_get_reference_data_returns_pdf_file_for_saved_owner_reference(
    tmp_path: Path,
) -> None:
    """
    観点：GetReferenceDataUseCaseが保存済みPDF参照元メタとファイル境界を結合すること
    確認：認証ユーザの参照元IDから共有データソース相対pathを開き、
    PDF配信用ファイルパスとapplication/pdfを返すこと
    """
    from backend.application.references.get_reference_data import (
        GetReferenceDataCommand,
        GetReferenceDataUseCase,
    )

    pdf_path = tmp_path / "manual" / "a.pdf"
    reference = _reference_data(path="manual/a.pdf")
    repository = FakeReferenceDeliveryRepository(
        references={(F003_USER_ID, REFERENCE_ID_VALUE): reference},
    )
    store = FakeReferenceStore(file_path=pdf_path)
    use_case = GetReferenceDataUseCase(
        repository=repository,
        reference_store=store,
    )

    result = use_case.execute(
        GetReferenceDataCommand(
            user_id=F003_USER_ID,
            reference_id=REFERENCE_ID_VALUE,
            trace_id=TRACE_ID_VALUE,
        ),
    )

    assert repository.requested == [(F003_USER_ID, REFERENCE_ID_VALUE)]
    assert store.opened_paths == ["manual/a.pdf"]
    assert result.file_path == pdf_path
    assert result.mime_type == "application/pdf"


def test_get_reference_data_rejects_missing_reference_without_file_access(
    tmp_path: Path,
) -> None:
    """
    観点：GetReferenceDataUseCaseが対象なしをファイルアクセス前に止めること
    確認：参照元IDが認証ユーザの保存済み回答に紐づかない場合はNOT_FOUNDとなり、
    ReferenceStoreを呼び出さないこと
    """
    from backend.application.references.get_reference_data import (
        GetReferenceDataCommand,
        GetReferenceDataUseCase,
    )

    repository = FakeReferenceDeliveryRepository(
        references={(F003_USER_ID, REFERENCE_ID_VALUE): None},
    )
    store = FakeReferenceStore(file_path=tmp_path / "manual" / "a.pdf")
    use_case = GetReferenceDataUseCase(
        repository=repository,
        reference_store=store,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetReferenceDataCommand(
                user_id=F003_USER_ID,
                reference_id=REFERENCE_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.NOT_FOUND
    assert raised.value.trace is False
    assert store.opened_paths == []


def test_get_reference_data_rejects_other_user_reference_without_file_access(
    tmp_path: Path,
) -> None:
    """
    観点：GetReferenceDataUseCaseが認証ユーザ所有外の参照元を配信しないこと
    確認：別ユーザに紐づく同一参照元IDはNOT_FOUNDとなり、
    ReferenceStoreを呼び出さないこと
    """
    from backend.application.references.get_reference_data import (
        GetReferenceDataCommand,
        GetReferenceDataUseCase,
    )

    repository = FakeReferenceDeliveryRepository(
        references={(OTHER_USER_ID, REFERENCE_ID_VALUE): _reference_data(path="x.pdf")},
    )
    store = FakeReferenceStore(file_path=tmp_path / "x.pdf")
    use_case = GetReferenceDataUseCase(
        repository=repository,
        reference_store=store,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetReferenceDataCommand(
                user_id=F003_USER_ID,
                reference_id=REFERENCE_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.NOT_FOUND
    assert store.opened_paths == []


def test_get_reference_data_rejects_deleting_chat_without_file_access(
    tmp_path: Path,
) -> None:
    """
    観点：GetReferenceDataUseCaseが削除中チャットに紐づく参照元を配信しないこと
    確認：Repository境界のCONFLICTを返し、共有データソースのPDFを開かないこと
    """
    from backend.application.references.get_reference_data import (
        GetReferenceDataCommand,
        GetReferenceDataUseCase,
    )

    repository = FakeReferenceDeliveryRepository(
        references={},
        errors={
            (F003_USER_ID, REFERENCE_ID_VALUE): AppError(
                error_type=ErrorType.CONFLICT,
                trace=False,
                diagnostic_message="削除中のチャットです。",
            ),
        },
    )
    store = FakeReferenceStore(file_path=tmp_path / "manual" / "a.pdf")
    use_case = GetReferenceDataUseCase(
        repository=repository,
        reference_store=store,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetReferenceDataCommand(
                user_id=F003_USER_ID,
                reference_id=REFERENCE_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.CONFLICT
    assert raised.value.trace is False
    assert store.opened_paths == []


def test_get_reference_data_rejects_non_pdf_reference_type(tmp_path: Path) -> None:
    """
    観点：GetReferenceDataUseCaseがPDF以外の参照元種別を配信対象にしないこと
    確認：保存済みメタのsource_typeがpdf以外の場合はFORBIDDENとなり、
    共有データソースのファイルを開かないこと
    """
    from backend.application.references.get_reference_data import (
        GetReferenceDataCommand,
        GetReferenceDataUseCase,
    )

    repository = FakeReferenceDeliveryRepository(
        references={
            (F003_USER_ID, REFERENCE_ID_VALUE): _reference_data(
                source_type="html",
                path="manual/a.html",
            ),
        },
    )
    store = FakeReferenceStore(file_path=tmp_path / "manual" / "a.html")
    use_case = GetReferenceDataUseCase(
        repository=repository,
        reference_store=store,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetReferenceDataCommand(
                user_id=F003_USER_ID,
                reference_id=REFERENCE_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.FORBIDDEN
    assert store.opened_paths == []


def test_get_reference_data_returns_store_missing_file_as_not_found(
    tmp_path: Path,
) -> None:
    """
    観点：GetReferenceDataUseCaseがPDFメタ存在時の実ファイル欠損を扱うこと
    確認：ReferenceStoreのNOT_FOUNDを返し、対象相対pathだけを開こうとすること
    """
    from backend.application.references.get_reference_data import (
        GetReferenceDataCommand,
        GetReferenceDataUseCase,
    )

    repository = FakeReferenceDeliveryRepository(
        references={
            (F003_USER_ID, REFERENCE_ID_VALUE): _reference_data(path="lost.pdf"),
        },
    )
    store = FakeReferenceStore(
        file_path=tmp_path / "lost.pdf",
        error=AppError(
            error_type=ErrorType.NOT_FOUND,
            trace=False,
            diagnostic_message="参照元PDFが見つかりません。",
        ),
    )
    use_case = GetReferenceDataUseCase(
        repository=repository,
        reference_store=store,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetReferenceDataCommand(
                user_id=F003_USER_ID,
                reference_id=REFERENCE_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.NOT_FOUND
    assert raised.value.trace is False
    assert store.opened_paths == ["lost.pdf"]


def test_get_reference_data_returns_store_read_failure_as_system(
    tmp_path: Path,
) -> None:
    """
    観点：GetReferenceDataUseCaseがPDFメタ存在時のファイル読込失敗を扱うこと
    確認：ReferenceStoreのSYSTEMを返し、対象相対pathだけを開こうとすること
    """
    from backend.application.references.get_reference_data import (
        GetReferenceDataCommand,
        GetReferenceDataUseCase,
    )

    repository = FakeReferenceDeliveryRepository(
        references={
            (F003_USER_ID, REFERENCE_ID_VALUE): _reference_data(path="broken.pdf"),
        },
    )
    store = FakeReferenceStore(
        file_path=tmp_path / "broken.pdf",
        error=AppError(
            error_type=ErrorType.SYSTEM,
            trace=True,
            diagnostic_message="参照元PDFを読み込めません。",
        ),
    )
    use_case = GetReferenceDataUseCase(
        repository=repository,
        reference_store=store,
    )

    with pytest.raises(AppError) as raised:
        use_case.execute(
            GetReferenceDataCommand(
                user_id=F003_USER_ID,
                reference_id=REFERENCE_ID_VALUE,
                trace_id=TRACE_ID_VALUE,
            ),
        )

    assert raised.value.error_type is ErrorType.SYSTEM
    assert raised.value.trace is True
    assert store.opened_paths == ["broken.pdf"]


def _reference_data(
    *,
    path: str,
    source_type: str = "pdf",
) -> DisplayReferenceData:
    return DisplayReferenceData(
        reference_id=REFERENCE_ID_VALUE,
        position=1,
        source_type=source_type,
        label="資料A",
        path=path,
        page_start=2,
        page_end=3,
    )
