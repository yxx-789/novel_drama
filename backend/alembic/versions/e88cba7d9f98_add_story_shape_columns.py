"""add story shape columns

Revision ID: e88cba7d9f98
Revises: a1b2c3d4e5f6
Create Date: 2026-08-12 14:43:16.202435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e88cba7d9f98'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 存量项目回填 story_shape='open'（现有项目已生成 500 章级架构，天然连载形态）、M=NULL
    op.add_column('projects', sa.Column('story_shape', sa.String(length=20), nullable=False, server_default='open'))
    op.add_column('projects', sa.Column('total_chapters_target', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'total_chapters_target')
    op.drop_column('projects', 'story_shape')
