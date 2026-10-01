"""Bond slashing on fraudulent telemetry; fail-closed oracle fallbacks."""
import json
import pytest
from conftest import *


@pytest.fixture
def c(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    deposit(c, direct_vm, direct_alice, 5 * ATTO)
    return c


def slashed(c, direct_vm, who, body):
    k, out = onboard(c, direct_vm, who, body=body)
    return k, out


# ---------------------------------------------------------------- fraud: slash
def test_negative_revenue_claiming_aaa_is_slashed(c, direct_vm, direct_bob):
    body = telemetry(monthly_revenue_usd=-500_000, claimed_rating="AAA")
    k, out = slashed(c, direct_vm, direct_bob, body)
    assert out["status"] == "REJECTED" and out["reason"] == "IMPOSSIBLE_NEGATIVE_VALUE"
    assert out["bond_slashed"] == str(BOND)


def test_slash_moves_bond_to_insurance_reserve(c, direct_vm, direct_bob):
    slashed(c, direct_vm, direct_bob, telemetry(monthly_revenue_usd=-1))
    m = c.get_pool_metrics()
    assert m["insurance_reserve"] == str(BOND) and m["bonds_held"] == "0" and m["cumulative_slashed"] == str(BOND)


def test_slash_preserves_cash_invariant(c, direct_vm, direct_bob):
    slashed(c, direct_vm, direct_bob, telemetry(monthly_revenue_usd=-1))
    assert expected_balance(c) == 5 * ATTO + BOND  # bond stays in the contract


def test_slashed_profile_zeroed(c, direct_vm, direct_bob):
    k, _ = slashed(c, direct_vm, direct_bob, telemetry(monthly_revenue_usd=-1))
    p = c.get_credit_profile(k)
    assert p["status"] == "REJECTED" and p["credit_limit"] == "0" and p["underwriting_bond"] == "0"


def test_slashed_address_cannot_reapply(c, direct_vm, direct_bob):
    slashed(c, direct_vm, direct_bob, telemetry(monthly_revenue_usd=-1))
    send(direct_vm, direct_bob, BOND)
    with direct_vm.expect_revert("banned"):
        c.apply_for_credit("Again", URL, ATTO)


def test_slashed_cannot_draw(c, direct_vm, direct_bob):
    slashed(c, direct_vm, direct_bob, telemetry(monthly_revenue_usd=-1))
    with direct_vm.expect_revert("REJECTED"):
        draw(c, direct_vm, direct_bob, 1)


@pytest.mark.parametrize("field", ["monthly_opex_usd", "monthly_burn_usd", "treasury_usd"])
def test_any_negative_figure_is_fraud(c, direct_vm, direct_bob, field):
    k, out = slashed(c, direct_vm, direct_bob, telemetry(**{field: -10}))
    assert out["status"] == "REJECTED"


def test_burn_below_opex_is_impossible(c, direct_vm, direct_bob):
    k, out = slashed(c, direct_vm, direct_bob, telemetry(monthly_burn_usd=50_000))
    assert out["reason"] == "BURN_BELOW_OPEX"


def test_duplicate_transaction_ids_are_fake_logs(c, direct_vm, direct_bob):
    txs = [{"tx": "0xabc", "amount_usd": 50_000}, {"tx": "0xabc", "amount_usd": 50_000}]
    k, out = slashed(c, direct_vm, direct_bob, telemetry(transactions=txs, proof_sha256=proof(txs),
                                                         verified_onchain_inflows_usd=100_000))
    assert out["reason"] == "DUPLICATE_TRANSACTION"


def test_tampered_proof_digest_is_slashed(c, direct_vm, direct_bob):
    k, out = slashed(c, direct_vm, direct_bob, telemetry(proof_sha256="00" * 32))
    assert out["reason"] == "PROOF_DIGEST_MISMATCH"


def test_missing_digest_with_log_is_slashed(c, direct_vm, direct_bob):
    k, out = slashed(c, direct_vm, direct_bob, telemetry(proof_sha256=None))
    assert out["reason"] == "PROOF_DIGEST_MISMATCH"


def test_digest_accepts_0x_prefix_and_uppercase(c, direct_vm, direct_bob):
    txs, inflow = txlog()
    k, out = slashed(c, direct_vm, direct_bob, telemetry(transactions=txs, proof_sha256="0x" + proof(txs).upper(),
                                                         verified_onchain_inflows_usd=inflow))
    assert out["status"] == "ACTIVE"


def test_inflow_total_must_match_log(c, direct_vm, direct_bob):
    k, out = slashed(c, direct_vm, direct_bob, telemetry(verified_onchain_inflows_usd=9_999_999))
    assert out["reason"] == "INFLOW_TOTAL_MISMATCH"


def test_non_positive_transaction_amount_is_fraud(c, direct_vm, direct_bob):
    txs = [{"tx": "0x1", "amount_usd": -5}]
    k, out = slashed(c, direct_vm, direct_bob, telemetry(transactions=txs, proof_sha256=proof(txs),
                                                         verified_onchain_inflows_usd=-5))
    assert out["reason"] == "TRANSACTION_LOG_INVALID"


def test_malformed_transaction_entry_is_fraud(c, direct_vm, direct_bob):
    k, out = slashed(c, direct_vm, direct_bob, telemetry(transactions=["x"], proof_sha256=proof(["x"])))
    assert out["reason"] == "TRANSACTION_LOG_INVALID"


def test_arr_claim_inconsistent_with_revenue(c, direct_vm, direct_bob):
    k, out = slashed(c, direct_vm, direct_bob, telemetry(claimed_arr_usd=9_000_000))
    assert out["reason"] == "ARR_INCONSISTENT_WITH_REVENUE"


def test_arr_claim_within_tolerance_is_ok(c, direct_vm, direct_bob):
    k, out = slashed(c, direct_vm, direct_bob, telemetry(claimed_arr_usd=2_510_000))
    assert out["status"] == "ACTIVE"


def test_fraud_decision_is_deterministic_not_llm(c, direct_vm, direct_bob):
    # a fully lenient model cannot rescue impossible numbers
    review(direct_vm, "CLEAN", 0)
    k, out = slashed(c, direct_vm, direct_bob, telemetry(monthly_revenue_usd=-1))
    assert out["status"] == "REJECTED"


# ------------------------------------------------------------ fail-closed paths
@pytest.mark.parametrize("status", [404, 500, 502, 503, 429, 403, 301])
def test_http_failures_are_inconclusive_and_refund(c, direct_vm, direct_bob, status):
    feed(direct_vm, "nope", status=status); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    out = assess(c, direct_vm, key(c, direct_vm, direct_bob))
    assert out["status"] == "INCONCLUSIVE" and out["bond_refunded"] == str(BOND)


def test_inconclusive_releases_bond_accounting(c, direct_vm, direct_bob):
    feed(direct_vm, "x", status=404); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    assess(c, direct_vm, key(c, direct_vm, direct_bob))
    assert c.get_pool_metrics()["bonds_held"] == "0"
    assert c.get_pool_metrics()["insurance_reserve"] == "0"
    assert expected_balance(c) == 5 * ATTO


def test_inconclusive_profile_state(c, direct_vm, direct_bob):
    feed(direct_vm, "x", status=500); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    k = key(c, direct_vm, direct_bob)
    assess(c, direct_vm, k)
    p = c.get_credit_profile(k)
    assert p["status"] == "INCONCLUSIVE" and p["credit_limit"] == "0" and p["underwriting_bond"] == "0"


def test_inconclusive_borrower_can_reapply(c, direct_vm, direct_bob):
    feed(direct_vm, "x", status=500); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    assess(c, direct_vm, key(c, direct_vm, direct_bob))
    feed(direct_vm, telemetry())
    apply(c, direct_vm, direct_bob)
    assert assess(c, direct_vm, key(c, direct_vm, direct_bob))["status"] == "ACTIVE"
    assert c.get_borrower_count() == 1  # same registry slot reused


def test_inconclusive_borrower_is_not_banned(c, direct_vm, direct_bob):
    feed(direct_vm, "x", status=404); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    assess(c, direct_vm, key(c, direct_vm, direct_bob))
    apply(c, direct_vm, direct_bob)  # must not revert


def test_malformed_json_is_inconclusive(c, direct_vm, direct_bob):
    feed(direct_vm, "{not json"); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    out = assess(c, direct_vm, key(c, direct_vm, direct_bob))
    assert out["status"] == "INCONCLUSIVE" and out["reason"] == "MALFORMED"


def test_non_object_json_is_inconclusive(c, direct_vm, direct_bob):
    feed(direct_vm, "[1,2,3]"); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    out = assess(c, direct_vm, key(c, direct_vm, direct_bob))
    assert out["status"] == "INCONCLUSIVE"


def test_missing_required_fields_is_inconclusive(c, direct_vm, direct_bob):
    feed(direct_vm, {"monthly_revenue_usd": 5}); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    assert assess(c, direct_vm, key(c, direct_vm, direct_bob))["reason"] == "MISSING_REQUIRED_FIELDS"


def test_boolean_is_not_a_number(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, body=telemetry(monthly_revenue_usd=True))
    assert out["status"] == "INCONCLUSIVE"


def test_string_numbers_rejected(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, body=telemetry(treasury_usd="700000"))
    assert out["status"] == "INCONCLUSIVE"


def test_zero_revenue_is_unusable_not_fraud(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, body=telemetry(monthly_revenue_usd=0, claimed_arr_usd=None))
    assert out["status"] == "INCONCLUSIVE" and out["reason"] == "NO_REVENUE"
    assert c.get_pool_metrics()["cumulative_slashed"] == "0"


def test_oversized_body_is_malformed(c, direct_vm, direct_bob):
    feed(direct_vm, "{" + " " * 70_000 + "}"); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    assert assess(c, direct_vm, key(c, direct_vm, direct_bob))["reason"] == "MALFORMED"


def test_pending_profile_never_activates_without_consensus_data(c, direct_vm, direct_bob):
    feed(direct_vm, "x", status=404); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    k = key(c, direct_vm, direct_bob)
    assess(c, direct_vm, k)
    with direct_vm.expect_revert("INCONCLUSIVE"):
        draw(c, direct_vm, direct_bob, 1)
