"""Prometheus metrics — exposed on /metrics."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# HTTP layer
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests handled.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency.",
    ["method", "path"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# Pipeline
GRAPH_NODE_DURATION = Histogram(
    "graph_node_duration_seconds",
    "Time spent in each graph node.",
    ["node"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30],
)
CLASSIFICATION_TOTAL = Counter(
    "classification_total",
    "Classifications by category and priority.",
    ["category", "priority"],
)
ESCALATION_TOTAL = Counter(
    "escalation_total",
    "Escalations triggered, by reason.",
    ["reason"],
)
HITL_RESOLUTION_TOTAL = Counter(
    "hitl_resolution_total",
    "HITL resolutions, by action.",
    ["action"],
)

# LLM
LLM_REQUESTS = Counter(
    "llm_requests_total",
    "LLM calls.",
    ["provider", "model", "operation", "outcome"],
)
LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "LLM call latency.",
    ["provider", "model", "operation"],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120],
)
LLM_TOKENS = Counter(
    "llm_tokens_total",
    "LLM tokens consumed.",
    ["provider", "model", "kind"],
)
LLM_COST_USD = Counter(
    "llm_cost_usd_total",
    "Estimated USD cost of LLM calls.",
    ["provider", "model"],
)

# Workers
WORKER_QUEUE_DEPTH = Gauge(
    "worker_queue_depth",
    "Approximate Arq queue depth.",
    ["queue"],
)
