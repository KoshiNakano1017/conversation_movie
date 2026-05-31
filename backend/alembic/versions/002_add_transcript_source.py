"""add transcript source column and remove whisper-specific fields

Revision ID: 002
Revises: 001
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # source カラムを追加（"paste" がデフォルト）
    op.add_column(
        "transcriptions",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="paste",
            comment="入力ソース: paste（テキスト貼り付け）| whisper（音声自動文字起こし）",
        ),
    )

    # 既存の Whisper専用カラムを削除（001で作成済みの場合）
    try:
        op.drop_column("transcriptions", "model_name")
        op.drop_column("transcriptions", "word_error_rate")
    except Exception:
        pass


def downgrade() -> None:
    op.drop_column("transcriptions", "source")
    op.add_column(
        "transcriptions",
        sa.Column("model_name", sa.String(50), nullable=False, server_default="medium"),
    )
    op.add_column(
        "transcriptions",
        sa.Column("word_error_rate", sa.Float),
    )
