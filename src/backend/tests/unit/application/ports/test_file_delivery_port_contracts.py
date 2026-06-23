from __future__ import annotations

from dataclasses import is_dataclass


def test_file_delivery_ports_are_declared_for_f006_boundaries() -> None:
    """
    観点：参照元PDF取得とCodex成果物配信がapplication層のファイルPortへ依存すること
    確認：ReferenceStorePort、ArtifactStorePort、SavedArtifactDeletionPortをimportできること
    """
    from backend.application.ports.filesystem.interface import (
        ArtifactStorePort,
        ReferenceStorePort,
        SavedArtifactDeletionPort,
    )

    ports = (ReferenceStorePort, ArtifactStorePort, SavedArtifactDeletionPort)

    assert all(type(port).__name__ == "_ProtocolMeta" for port in ports)


def test_file_delivery_dtos_are_dataclasses_not_raw_paths() -> None:
    """
    観点：ファイル配信境界が裸の文字列や実装詳細ではなくDTOで値を返すこと
    確認：OpenedReferenceFile、OpenedArtifactFile、SavedArtifactFileを
    dataclassとしてimportできること
    """
    from backend.application.ports.filesystem.dto import (
        OpenedArtifactFile,
        OpenedReferenceFile,
        SavedArtifactFile,
    )

    dto_classes = (OpenedReferenceFile, OpenedArtifactFile, SavedArtifactFile)

    assert all(is_dataclass(dto_class) for dto_class in dto_classes)


def test_saved_artifact_deletion_port_exposes_f007_delete_methods() -> None:
    """
    観点：保存済み成果物削除Portがチャット単位とアカウント単位の物理削除境界を表すこと
    確認：storage_path一覧削除とuser_id単位ディレクトリ削除の公開メソッドが
    Protocolに定義されること
    """
    from backend.application.ports.filesystem.interface import SavedArtifactDeletionPort

    assert hasattr(SavedArtifactDeletionPort, "delete_saved_files")
    assert hasattr(SavedArtifactDeletionPort, "delete_user_saved_artifacts")
