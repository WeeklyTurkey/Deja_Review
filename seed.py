"""Seed memories and deterministic demo snippets.

Seeds: 10 team memories, two per category across 5 categories.
Snippets: 5 short realistic payments/web Python snippets, 10-25 lines.
"""

from __future__ import annotations

import memory

SEED_MEMORIES: list[str] = [
    # 1. Type hints on public functions
    "Payments team requires type hints on all public functions.",
    "All public functions must declare parameter and return types; untyped defs get flagged.",
    # 2. logging instead of print()
    "Use the logging module instead of print() for all runtime output.",
    "print() is only allowed in CLI entry points; library and service code must use logging.",
    # 3. None checks on external API responses
    "Always None-check fields from external API responses before use.",
    "Never assume external API payloads contain a key; guard with .get() or explicit None checks.",
    # 4. Naming: snake_case, no single-letter names outside loops
    "Use snake_case for functions and variables; no single-letter names outside loop counters.",
    "Single-letter variable names are only acceptable as loop counters, never for data.",
    # 5. Error handling: no bare except, catch specific exceptions
    "Never use bare except: blocks; catch specific exceptions.",
    "Error handling must catch specific exception types and log the error context.",
]

SNIPPET_1 = '''"""payments.py - refund helper (violates the type-hint rule)."""

def calculate_refund(amount, fee_rate):
    refund = amount - (amount * fee_rate)
    return refund


def process_refund(payment, gateway):
    result = gateway.charge_refund(payment.id, payment.amount)
    return result
'''

SNIPPET_2 = '''"""ledger.py - payout helper (violates the type-hint rule again)."""

def compute_payout(balance, rate):
    payout = balance * rate
    return payout


def settle_payout(account, ledger):
    entry = ledger.create_entry(account.id, account.balance)
    return entry
'''

SNIPPET_3 = '''"""checkout.py - order logging (violates the logging rule)."""

import logging

logger = logging.getLogger(__name__)


def confirm_order(order_id: str, total: float) -> bool:
    print(f"Confirming order {order_id} for {total}")
    print("Order confirmed, sending receipt")
    logger.info("Receipt sent for order %s", order_id)
    return True
'''

SNIPPET_4 = '''"""webhooks.py - gateway webhook handler (None-check + error handling)."""

import logging

logger = logging.getLogger(__name__)


def handle_webhook(payload: dict) -> str:
    try:
        event = payload["event"]
        amount = payload["data"]["amount"]
    except:
        print("webhook failed")
        return "error"
    logger.info("Handled webhook event %s", event)
    return f"ok:{amount}"
'''

SNIPPET_5 = '''"""status.py - clean service health check (no issues expected)."""

import logging

logger = logging.getLogger(__name__)


def check_service_health(service_name: str, timeout_seconds: float) -> bool:
    """Return True when the named service responds within the timeout."""
    logger.info("Checking health of %s", service_name)
    try:
        latency = _ping_service(service_name, timeout_seconds)
    except TimeoutError:
        logger.warning("Health check timed out for %s", service_name)
        return False
    return latency < timeout_seconds
'''

SNIPPETS: dict[int, str] = {
    1: SNIPPET_1,
    2: SNIPPET_2,
    3: SNIPPET_3,
    4: SNIPPET_4,
    5: SNIPPET_5,
}

SNIPPET_TITLES: dict[int, str] = {
    1: "Snippet 1: refund helper missing type hints",
    2: "Snippet 2: payout helper missing type hints again",
    3: "Snippet 3: checkout logging uses print()",
    4: "Snippet 4: webhook handler None-check and error handling",
    5: "Snippet 5: clean health check",
}

SNIPPET_FILES: dict[int, str] = {
    1: "payments.py",
    2: "ledger.py",
    3: "checkout.py",
    4: "webhooks.py",
    5: "status.py",
}


def seed_project(project: str) -> int:
    """Retain all seed memories into the project's bank. Returns count retained."""
    count = 0
    for text in SEED_MEMORIES:
        memory.retain(project, text)
        count += 1
    return count


def get_snippet(n: int) -> str:
    return SNIPPETS[n]


if __name__ == "__main__":
    import sys

    project = sys.argv[1] if len(sys.argv) > 1 else "payments-service"
    n = seed_project(project)
    print(f"Seeded {n} memories into project '{project}'.")
