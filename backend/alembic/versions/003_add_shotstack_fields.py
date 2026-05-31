"""videos テーブルに Shotstack レンダリング関連カラムを追加

Revision ID: 003
Revises: 002
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column(
            "render_backend",
            sa.String(20),
            nullable=False,
            server_default="shotstack",
            comment="レンダリングバックエンド: shotstack | remotion",
        ),
    )
    op.add_column(
        "videos",
        sa.Column(
            "shotstack_render_id",
            sa.String(100),
            nullable=True,
            comment="Shotstack の render ID（ステータス追跡・課金確認用）",
        ),
    )


def downgrade() -> None:
    op.drop_column("videos", "shotstack_render_id")
    op.drop_column("videos", "render_backend")
