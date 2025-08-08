"""init

Revision ID: 0001_init
Revises: 
Create Date: 2025-08-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('employees',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('birthdate', sa.Date(), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('telegram_username', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_helper', sa.Boolean(), default=False),
        sa.Column('medbook_expiration', sa.Date(), nullable=True),
        sa.Column('medbook_notified', sa.Boolean(), default=False),
    )

    op.create_table('locations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('zone', sa.String(), nullable=True),
    )

    op.create_table('employee_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id')),
        sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id')),
        sa.Column('type', sa.String(), nullable=False),  # 'allowed', 'preferred', 'forbidden', etc.
    )

    op.create_table('schedule_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
    )

    op.create_table('schedule_template_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('schedule_templates.id')),
        sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id')),
        sa.Column('num_employees', sa.Integer(), nullable=False),
    )

    op.create_table('schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id')),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id')),
    )


def downgrade():
    op.drop_table('schedules')
    op.drop_table('schedule_template_assignments')
    op.drop_table('schedule_templates')
    op.drop_table('employee_settings')
    op.drop_table('locations')
    op.drop_table('employees')
