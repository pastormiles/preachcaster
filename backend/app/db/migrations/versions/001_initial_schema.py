"""Initial schema - users, churches, podcast_settings, sermons

Revision ID: 001
Revises:
Create Date: 2025-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Churches table
    op.create_table(
        'churches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('youtube_channel_id', sa.String(100), nullable=True),
        sa.Column('youtube_access_token', sa.Text(), nullable=True),
        sa.Column('youtube_refresh_token', sa.Text(), nullable=True),
        sa.Column('youtube_token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_churches_id', 'churches', ['id'])
    op.create_index('ix_churches_slug', 'churches', ['slug'], unique=True)

    # Podcast settings table
    op.create_table(
        'podcast_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('church_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('author', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('artwork_url', sa.String(500), nullable=True),
        sa.Column('category', sa.String(100), default='Religion & Spirituality'),
        sa.Column('subcategory', sa.String(100), default='Christianity'),
        sa.Column('language', sa.String(10), default='en'),
        sa.Column('explicit', sa.String(5), default='no'),
        sa.Column('website_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['church_id'], ['churches.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('church_id')
    )
    op.create_index('ix_podcast_settings_id', 'podcast_settings', ['id'])

    # Sermons table
    op.create_table(
        'sermons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('church_id', sa.Integer(), nullable=False),
        sa.Column('youtube_video_id', sa.String(20), nullable=False),
        sa.Column('youtube_url', sa.String(255), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('speaker', sa.String(255), nullable=True),
        sa.Column('scripture_references', sa.String(500), nullable=True),
        sa.Column('sermon_date', sa.DateTime(), nullable=True),
        sa.Column('audio_url', sa.String(500), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('transcript_json', sa.JSON(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('discussion_guide', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['church_id'], ['churches.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sermons_id', 'sermons', ['id'])
    op.create_index('ix_sermons_youtube_video_id', 'sermons', ['youtube_video_id'])


def downgrade() -> None:
    op.drop_table('sermons')
    op.drop_table('podcast_settings')
    op.drop_table('churches')
    op.drop_table('users')
