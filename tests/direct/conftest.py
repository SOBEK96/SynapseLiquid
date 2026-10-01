"""Shared helpers for SynapseLiquid direct-mode tests (in-memory GenVM)."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

CONTRACT = "contracts/synapse_liquid.py"
ATTO = 10**18
BOND = ATTO // 10
URL = "https://telemetry.example.com/borrower.json"
DAY = 86400
YEAR = 365 * DAY


def proof(txs):
    canon = json.dumps(txs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def txlog(total=150_000, n=3):
    each = total // n
    txs = [{"tx": f"0x{i:064x}", "amount_usd": each} for i in range(1, n + 1)]
    return txs, each * n


def telemetry(**over):
    """Aether-class telemetry: AAA on the default 3 GEN request."""
    txs, inflow = txlog()
    body = {
        "monthly_revenue_usd": 208_334,
        "monthly_opex_usd": 100_000,
        "monthly_burn_usd": 233_334,
        "treasury_usd": 700_000,
        "existing_annual_debt_service_usd": 0,
        "claimed_arr_usd": 2_500_008,
        "transactions": txs,
        "proof_sha256": proof(txs),
        "verified_onchain_inflows_usd": inflow,
        "narrative": "Enterprise SaaS, diversified customer base.",
    }
    body.update(over)
    return {k: v for k, v in body.items() if v is not None}


def hyperscale(**over):
    txs, inflow = txlog(12_000)
    body = {
        "monthly_revenue_usd": 60_000,
        "monthly_opex_usd": 180_000,
        "monthly_burn_usd": 260_000,
        "treasury_usd": 400_000,
        "transactions": txs,
        "proof_sha256": proof(txs),
        "verified_onchain_inflows_usd": inflow,
        "narrative": "Aggressive growth spend.",
    }
    body.update(over)
    return body


def feed(vm, body, status=200):
    raw = body if isinstance(body, str) else json.dumps(body)
    vm.clear_mocks()
    vm.mock_web(r".*", {"status": status, "body": raw})
    if getattr(vm, "_last_review", None):  # clear_mocks also drops the LLM mock
        review(vm, *vm._last_review)


def review(vm, flag="CLEAN", notches=0, rationale="Committee review."):
    # Double-encoded: the harness json.loads()s the mock once, the SDK again.
    vm._last_review = (flag, notches, rationale)
    vm.mock_llm(r"(?s).*", json.dumps(json.dumps(
        {"risk_flag": flag, "notches_down": notches, "rationale": rationale})))


def send(vm, who, value=0):
    vm.sender = who
    vm.value = value


def deposit(c, vm, who, amount):
    send(vm, who, amount)
    out = c.deposit_liquidity()
    vm.value = 0
    return out


def apply(c, vm, who, name="Aether Infrastructure", limit=3 * ATTO, uri=URL, value=BOND):
    send(vm, who, value)
    out = c.apply_for_credit(name, uri, limit)
    vm.value = 0
    return out


def key(c, vm, who):
    vm.sender = who
    return c.whoami()


def assess(c, vm, borrower_key, caller=None):
    if caller is not None:
        vm.sender = caller
    vm.value = 0
    return c.assess_credit_consensus(borrower_key)


def onboard(c, vm, who, body=None, limit=3 * ATTO, flag="CLEAN", notches=0, name="Aether Infrastructure"):
    """apply + assess against a mocked feed; returns (key, assessment)."""
    feed(vm, telemetry() if body is None else body)
    review(vm, flag, notches)
    apply(c, vm, who, name=name, limit=limit)
    k = key(c, vm, who)
    return k, assess(c, vm, k)


def advance(vm, seconds):
    """Move the block clock forward."""
    cur = datetime.fromisoformat(vm._datetime.replace("Z", "+00:00"))
    vm.warp((cur + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))


def draw(c, vm, who, amount):
    send(vm, who)
    return c.drawdown_credit(amount)


def repay(c, vm, who, value):
    send(vm, who, value)
    out = c.service_debt()
    vm.value = 0
    return out


def expected_balance(c):
    """What the contract's cash must equal; direct mode does not move native value."""
    m = c.get_pool_metrics()
    return (int(m["total_deposited"]) - int(m["borrowed_liquidity"])
            + int(m["insurance_reserve"]) + int(m["bonds_held"]))
