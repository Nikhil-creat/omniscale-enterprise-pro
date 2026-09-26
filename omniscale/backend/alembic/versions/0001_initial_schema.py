"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-26

OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

subscription_tier = postgresql.ENUM("free", "pro", "enterprise", name="subscriptiontier")
subscription_status = postgresql.ENUM(
    "inactive", "active", "past_due", "canceled", name="subscriptionstatus"
)
job_status = postgresql.ENUM("pending", "running", "succeeded", "failed", name="jobstatus")


def upgrade() -> None:
    bind = op.get_bind()
    subscription_tier.create(bind, checkfirst=True)
    subscription_status.create(bind, checkfirst=True)
    job_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean, server_default=sa.false()),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_stripe_customer_id", "users", ["stripe_customer_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("key_prefix", sa.String(12)),
        sa.Column("hashed_key", sa.String(255), unique=True),
        sa.Column("name", sa.String(120), server_default="default"),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column("tier", subscription_tier, nullable=False, server_default="free"),
        sa.Column("status", subscription_status, nullable=False, server_default="inactive"),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("event_type", sa.String(120)),
        sa.Column("stripe_event_id", sa.String(255), unique=True, nullable=True),
        sa.Column("amount_cents", sa.Integer, nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("raw_payload", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("filename", sa.String(500)),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("vector_namespace", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    op.create_table(
        "inference_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("job_type", sa.String(50)),
        sa.Column("status", job_status, server_default="pending"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_inference_jobs_user_id", "inference_jobs", ["user_id"])
    op.create_index("ix_inference_jobs_celery_task_id", "inference_jobs", ["celery_task_id"])


def downgrade() -> None:
    op.drop_table("inference_jobs")
    op.drop_table("documents")
    op.drop_table("audit_logs")
    op.drop_table("subscriptions")
    op.drop_table("api_keys")
    op.drop_table("users")
    bind = op.get_bind()
    job_status.drop(bind, checkfirst=True)
    subscription_status.drop(bind, checkfirst=True)
    subscription_tier.drop(bind, checkfirst=True)
