"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-26 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- enums ----
    msg_source = sa.Enum("chat", "web_form", "email", "api", name="message_source")
    ticket_status = sa.Enum(
        "received", "classified", "enriched", "routed",
        "awaiting_review", "resolved", "failed", name="ticket_status"
    )
    ticket_handled_by = sa.Enum("auto", "human", "hybrid", name="ticket_handled_by")
    ticket_category = sa.Enum(
        "bug_report", "feature_request", "billing_issue",
        "technical_question", "incident_outage", name="ticket_category"
    )
    ticket_priority = sa.Enum("low", "medium", "high", name="ticket_priority")
    routing_queue = sa.Enum(
        "engineering", "billing", "product", "it_security", "fallback",
        name="routing_queue"
    )
    routing_decided_by = sa.Enum("auto", "hitl", name="routing_decided_by")
    escalation_status = sa.Enum(
        "pending", "accepted", "edited", "rejected", "expired",
        name="escalation_status"
    )

    # ---- messages ----
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", msg_source, nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("raw_payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("customer_id", sa.String(64), nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_customer_id", "messages", ["customer_id"])
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_correlation_id", "messages", ["correlation_id"])

    # ---- tickets ----
    op.create_table(
        "tickets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("status", ticket_status, nullable=False, server_default="received"),
        sa.Column("handled_by", ticket_handled_by, nullable=True),
        sa.Column("summary", sa.String(2000), nullable=True),
        sa.Column("final_output", JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tickets_tenant_id", "tickets", ["tenant_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_trace_id", "tickets", ["trace_id"])

    # ---- prompt_versions ----
    op.create_table(
        "prompt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("template_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", "template_hash", name="uq_prompt_name_hash"),
    )
    op.create_index("ix_prompt_versions_name", "prompt_versions", ["name"])

    # ---- classifications ----
    op.create_table(
        "classifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sa.String(1000), nullable=True),
        sa.Column("prompt_version_id", UUID(as_uuid=True), sa.ForeignKey("prompt_versions.id"), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("raw_output", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_classifications_category", "classifications", ["category"])
    op.create_index("ix_classifications_priority", "classifications", ["priority"])

    # ---- enrichments ----
    op.create_table(
        "enrichments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("issue_summary", sa.String(1000), nullable=True),
        sa.Column("affected_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("error_codes", JSONB(), nullable=False, server_default="[]"),
        sa.Column("invoice_amounts_usd", JSONB(), nullable=False, server_default="[]"),
        sa.Column("urgency_signals", JSONB(), nullable=False, server_default="[]"),
        sa.Column("detected_language", sa.String(8), nullable=True, server_default="en"),
        sa.Column("raw_output", JSONB(), nullable=True),
        sa.Column("prompt_version_id", UUID(as_uuid=True), sa.ForeignKey("prompt_versions.id"), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ---- routing_decisions ----
    op.create_table(
        "routing_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("queue", routing_queue, nullable=False),
        sa.Column("sla_minutes", sa.Integer(), nullable=False),
        sa.Column("rationale", sa.String(1000), nullable=True),
        sa.Column("decided_by", routing_decided_by, nullable=False, server_default="auto"),
        sa.Column("needs_human", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_routing_decisions_queue", "routing_decisions", ["queue"])

    # ---- escalations ----
    op.create_table(
        "escalations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("status", escalation_status, nullable=False, server_default="pending"),
        sa.Column("reasons", JSONB(), nullable=False, server_default="[]"),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("interrupt_id", sa.String(64), nullable=True),
        sa.Column("proposed_reviewer", sa.String(128), nullable=True),
        sa.Column("resolution", JSONB(), nullable=True),
        sa.Column("resolved_by", sa.String(128), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_escalations_ticket_id", "escalations", ["ticket_id"])
    op.create_index("ix_escalations_thread_id", "escalations", ["thread_id"])
    op.create_index("ix_escalations_status", "escalations", ["status"])
    op.create_index("ix_escalations_status_created", "escalations", ["status", "created_at"])

    # ---- audit_log ----
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("before_state", JSONB(), nullable=True),
        sa.Column("after_state", JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("extra", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_ticket_id", "audit_log", ["ticket_id"])
    op.create_index("ix_audit_log_event", "audit_log", ["event"])
    op.create_index("ix_audit_log_correlation_id", "audit_log", ["correlation_id"])
    op.create_index("ix_audit_log_trace_id", "audit_log", ["trace_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # ---- llm_calls ----
    op.create_table(
        "llm_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_version_id", UUID(as_uuid=True), sa.ForeignKey("prompt_versions.id"), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="success"),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column("request", JSONB(), nullable=True),
        sa.Column("response", JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_calls_ticket_id", "llm_calls", ["ticket_id"])
    op.create_index("ix_llm_calls_tenant_id", "llm_calls", ["tenant_id"])
    op.create_index("ix_llm_calls_operation", "llm_calls", ["operation"])
    op.create_index("ix_llm_calls_provider", "llm_calls", ["provider"])
    op.create_index("ix_llm_calls_trace_id", "llm_calls", ["trace_id"])
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"])


def downgrade() -> None:
    op.drop_table("llm_calls")
    op.drop_table("audit_log")
    op.drop_table("escalations")
    op.drop_table("routing_decisions")
    op.drop_table("enrichments")
    op.drop_table("classifications")
    op.drop_table("prompt_versions")
    op.drop_table("tickets")
    op.drop_table("messages")
    for name in [
        "escalation_status",
        "routing_decided_by",
        "routing_queue",
        "ticket_priority",
        "ticket_category",
        "ticket_handled_by",
        "ticket_status",
        "message_source",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
