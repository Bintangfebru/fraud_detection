"""Initial schema — all FraudShield tables

Revision ID: 001
Revises: (none)
Create Date: 2026-05-28 00:00:00.000000

Tables created:
  - users
  - transactions
  - fraud_predictions
  - alerts
  - audit_logs
  - model_registry
  - thresholds
  - training_jobs
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    # ── transactions ──────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transaction_ref", sa.String(64), nullable=False, unique=True),
        sa.Column("amt", sa.Float(), nullable=False),
        sa.Column("merchant", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("cc_num_masked", sa.String(20), nullable=True),
        sa.Column("gender", sa.String(1), nullable=True),
        sa.Column("trans_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hour", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("amt_log", sa.Float(), nullable=True),
        sa.Column("amt_mean_per_card", sa.Float(), nullable=True),
        sa.Column("amt_ratio", sa.Float(), nullable=True),
        sa.Column("amt_std_per_card", sa.Float(), nullable=True),
        sa.Column("txn_count_per_card", sa.Integer(), nullable=True),
        sa.Column("unique_merchants", sa.Integer(), nullable=True),
        sa.Column("unique_categories", sa.Integer(), nullable=True),
        sa.Column("category_food_dining", sa.Integer(), nullable=True),
        sa.Column("category_gas_transport", sa.Integer(), nullable=True),
        sa.Column("category_grocery_pos", sa.Integer(), nullable=True),
        sa.Column("category_kids_pets", sa.Integer(), nullable=True),
        sa.Column("category_misc_net", sa.Integer(), nullable=True),
        sa.Column("category_misc_pos", sa.Integer(), nullable=True),
        sa.Column("category_personal_care", sa.Integer(), nullable=True),
        sa.Column("category_shopping_net", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_transactions_transaction_ref", "transactions", ["transaction_ref"])
    op.create_index("ix_transactions_trans_datetime", "transactions", ["trans_datetime"])
    op.create_index("ix_transactions_merchant", "transactions", ["merchant"])
    op.create_index("ix_transactions_category", "transactions", ["category"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])

    # ── fraud_predictions ─────────────────────────────────────────────────────
    op.create_table(
        "fraud_predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transaction_id", sa.String(36), nullable=False),
        sa.Column("transaction_ref", sa.String(64), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("features_snapshot", sa.JSON(), nullable=True),
        sa.Column("shap_values", sa.JSON(), nullable=True),
        sa.Column("is_confirmed_fraud", sa.Boolean(), nullable=True),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "predicted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_fp_transaction_ref", "fraud_predictions", ["transaction_ref"])
    op.create_index("ix_fp_status", "fraud_predictions", ["status"])
    op.create_index("ix_fp_risk_score", "fraud_predictions", ["risk_score"])
    op.create_index("ix_fp_predicted_at", "fraud_predictions", ["predicted_at"])
    op.create_index("ix_fp_is_confirmed_fraud", "fraud_predictions", ["is_confirmed_fraud"])

    # ── alerts ────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prediction_id", sa.String(36), nullable=False),
        sa.Column("transaction_ref", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_by", sa.String(64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_alerts_prediction_id", "alerts", ["prediction_id"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_is_resolved", "alerts", ["is_resolved"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_audit_actor", "audit_logs", ["actor"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_resource", "audit_logs", ["resource_type", "resource_id"])

    # ── model_registry ────────────────────────────────────────────────────────
    op.create_table(
        "model_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("model_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("model_path", sa.String(512), nullable=True),
        sa.Column("dataset_size", sa.Integer(), nullable=True),
        sa.Column("data_source", sa.String(32), server_default="synthetic"),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_by", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_model_registry_status", "model_registry", ["status"])
    op.create_index("ix_model_registry_model_id", "model_registry", ["model_id"])

    # ── thresholds ────────────────────────────────────────────────────────────
    op.create_table(
        "thresholds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fraud_threshold", sa.Float(), nullable=False),
        sa.Column("review_threshold", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("set_by", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_thresholds_is_active", "thresholds", ["is_active"])
    op.create_index("ix_thresholds_created_at", "thresholds", ["created_at"])

    # ── training_jobs ─────────────────────────────────────────────────────────
    op.create_table(
        "training_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(64), nullable=False, unique=True),
        sa.Column("model_type", sa.String(64), nullable=False),
        sa.Column("training_period", sa.String(32), nullable=False),
        sa.Column("validation_split", sa.String(16), nullable=False),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data_source", sa.String(32), nullable=True),
        sa.Column("dataset_size", sa.Integer(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("model_id", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("warning_message", sa.Text(), nullable=True),
        sa.Column("started_by", sa.String(64), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_training_jobs_status", "training_jobs", ["status"])
    op.create_index("ix_training_jobs_started_at", "training_jobs", ["started_at"])

    # ── Seed: initial threshold row ───────────────────────────────────────────
    op.execute("""
        INSERT INTO thresholds (id, fraud_threshold, review_threshold, is_active, set_by, notes)
        VALUES (
            gen_random_uuid()::text,
            0.75,
            0.45,
            true,
            'system',
            'Default thresholds set during initial migration.'
        )
    """)


def downgrade() -> None:
    op.drop_table("training_jobs")
    op.drop_table("thresholds")
    op.drop_table("model_registry")
    op.drop_table("audit_logs")
    op.drop_table("alerts")
    op.drop_table("fraud_predictions")
    op.drop_table("transactions")
    op.drop_table("users")
