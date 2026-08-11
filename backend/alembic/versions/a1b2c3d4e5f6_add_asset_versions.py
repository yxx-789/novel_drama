"""add asset_versions table

Revision ID: a1b2c3d4e5f6
Revises: 3bae85f20ef6
Create Date: 2026-08-11

回填 SQL 为 PostgreSQL 专用（gen_random_uuid/now）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3bae85f20ef6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('asset_versions',
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('asset_type', sa.String(length=50), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('content_text', sa.Text(), nullable=False),
    sa.Column('trigger_type', sa.String(length=20), nullable=False),
    sa.Column('guidance', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'asset_type', 'version', name='uq_asset_versions_project_type_version')
    )

    # 存量回填：现有 architecture/directory 内容作为 v1（trigger=manual）
    bind = op.get_bind()
    bind.execute(sa.text(
        """
        INSERT INTO asset_versions
            (id, project_id, asset_type, version, content_text, trigger_type, created_at, updated_at)
        SELECT gen_random_uuid(), project_id, asset_type, 1, content_text, 'manual', now(), now()
        FROM project_assets
        WHERE asset_type IN ('architecture', 'directory')
          AND content_text IS NOT NULL AND content_text != ''
        """
    ))


def downgrade() -> None:
    op.drop_table('asset_versions')
