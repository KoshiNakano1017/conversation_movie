"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── ENUMの作成 ───────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_status AS ENUM (
                'pending', 'uploading', 'transcribing', 'diarizing',
                'analyzing', 'generating_subtitles', 'generating_video',
                'generating_shorts', 'uploading_youtube',
                'completed', 'failed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE video_type AS ENUM ('full', 'shorts');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ─── テーブルの作成 ────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100)),
        sa.Column("avatar_url", sa.Text),
        sa.Column("youtube_refresh_token", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", postgresql.ENUM("pending", "uploading", "transcribing", "diarizing", "analyzing", "generating_subtitles", "generating_video", "generating_shorts", "uploading_youtube", "completed", "failed", "cancelled", name="job_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text),
        sa.Column("progress", sa.Integer, default=0),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("language", sa.String(10), default="ja"),
        sa.Column("speaker_count", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_jobs_user_id", "jobs", ["user_id"])
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_created_at", "jobs", ["created_at"])

    op.create_table(
        "audio_files",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("storage_bucket", sa.String(100), default="audio"),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("is_processed", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "transcriptions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("full_text", sa.Text, nullable=False),
        sa.Column("language", sa.String(10), nullable=False, default="ja"),
        sa.Column("model_name", sa.String(50), nullable=False, default="medium"),
        sa.Column("word_error_rate", sa.Float),
        sa.Column("segments", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "speaker_segments",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("speaker_label", sa.String(20), nullable=False),
        sa.Column("speaker_name", sa.String(100)),
        sa.Column("start_time", sa.Float, nullable=False),
        sa.Column("end_time", sa.Float, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("segment_index", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_speaker_segments_job_id", "speaker_segments", ["job_id"])
    op.create_index("idx_speaker_segments_start", "speaker_segments", ["job_id", "start_time"])

    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("summary_short", sa.Text, nullable=False),
        sa.Column("summary_medium", sa.Text, nullable=False),
        sa.Column("summary_detailed", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("themes", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("keywords", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("quotes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("sentiment_timeline", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("overall_sentiment", sa.String(20)),
        sa.Column("suggested_title", sa.Text),
        sa.Column("suggested_description", sa.Text),
        sa.Column("suggested_tags", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("model_name", sa.String(100), nullable=False, default="gemini-1.5-flash"),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "subtitles",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("storage_path", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "avatar_characters",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("personality", sa.Text, nullable=False),
        sa.Column("speech_style", sa.Text, nullable=False),
        sa.Column("image_path", sa.Text, nullable=False),
        sa.Column("animation_type", sa.String(50), default="bounce"),
        sa.Column("color_primary", sa.String(7), default="#FF6B6B"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("order_index", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "avatar_scripts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("avatar_characters.id"), nullable=False),
        sa.Column("script_text", sa.Text, nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=False),
        sa.Column("section", sa.String(50), nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_type", postgresql.ENUM("full", "shorts", name="video_type", create_type=False), nullable=False, server_default="full"),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("storage_bucket", sa.String(100), default="videos"),
        sa.Column("file_size_bytes", sa.BigInteger),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("fps", sa.Integer),
        sa.Column("thumbnail_path", sa.Text),
        sa.Column("render_time_seconds", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "youtube_publications",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("video_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("youtube_video_id", sa.String(20), nullable=False),
        sa.Column("youtube_url", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("tags", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("privacy_status", sa.String(20), nullable=False, default="private"),
        sa.Column("is_shorts", sa.Boolean, default=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("view_count", sa.Integer, default=0),
        sa.Column("like_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "job_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.String(10), nullable=False, default="info"),
        sa.Column("step", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_job_logs_job_id", "job_logs", ["job_id"])
    op.create_index("idx_job_logs_created_at", "job_logs", ["job_id", "created_at"])

    # ─── アバターキャラクターの初期データ ─────────────────────
    op.execute("""
        INSERT INTO avatar_characters (name, description, personality, speech_style, image_path, color_primary, order_index)
        VALUES
        (
            'ハカセ',
            '物知りで丁寧な博士キャラ',
            'あなたは知識豊富な博士です。難しい内容を分かりやすく解説するのが得意です。視聴者に対して丁寧で知的な話し方をします。',
            '「なるほど、これは興味深い！専門的に解説すると...」という口調。知的で丁寧。',
            '/assets/avatars/hakase/default.png',
            '#4ECDC4',
            0
        ),
        (
            'ツッコミちゃん',
            '明るくて好奇心旺盛なツッコミ役',
            'あなたは明るくてエネルギッシュなキャラクターです。意外な発見に驚き、視聴者と一緒に楽しむのが得意です。',
            '「え！それどういうこと？」「すごい！」という明るい口調。感嘆符を多用。',
            '/assets/avatars/tsukkomi/default.png',
            '#FF6B6B',
            1
        ),
        (
            'まとめロボ',
            '落ち着いたナレーターロボ',
            'あなたは冷静で論理的なロボットです。情報を整理してポイントをまとめるのが得意です。',
            '「ポイントを整理します。」「重要事項：」という落ち着いた口調。端的で明確。',
            '/assets/avatars/matomerobo/default.png',
            '#95E1D3',
            2
        );
    """)


def downgrade() -> None:
    op.drop_table("job_logs")
    op.drop_table("youtube_publications")
    op.drop_table("videos")
    op.drop_table("avatar_scripts")
    op.drop_table("avatar_characters")
    op.drop_table("subtitles")
    op.drop_table("analyses")
    op.drop_table("speaker_segments")
    op.drop_table("transcriptions")
    op.drop_table("audio_files")
    op.drop_table("jobs")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS job_status;")
    op.execute("DROP TYPE IF EXISTS video_type;")
