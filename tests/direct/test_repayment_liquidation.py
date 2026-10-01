"""Interest accrual, amortisation, closure, delinquency and liquidation."""
import pytest
from conftest import *


@pytest.fixture
def c(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    deposit(c, direct_vm, direct_alice, 5 * ATTO)
    return c


@pytest.fixture
def line(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, LINE)
    return k


# -------------------------------------------------------------------- accrual
def test_simple_interest_after_one_year(c, direct_vm, line):
    advance(direct_vm, YEAR)
    s = c.get_borrower_schedule(line)
    assert int(s["accrued_interest"]) == LINE * 400 // 10000  # 4% APR


def test_interest_is_linear_in_time(c, direct_vm, line):
    advance(direct_vm, 100 * DAY)
    a = int(c.get_borrower_schedule(line)["accrued_interest"])
    advance(direct_vm, 100 * DAY)
    b = int(c.get_borrower_schedule(line)["accrued_interest"])
    assert abs(b - 2 * a) <= 2


def test_no_interest_without_time(c, line):
    assert c.get_borrower_schedule(line)["accrued_interest"] == "0"


def test_interest_scales_with_rating_rate(c, direct_vm, direct_bob, direct_charlie):
    # an AAA line and a BB line (no on-chain corroboration caps the rating at BB)
    k1, _ = onboard(c, direct_vm, direct_bob, limit=ATTO)
    bb = telemetry(transactions=None, proof_sha256=None, verified_onchain_inflows_usd=None)
    k2, out = onboard(c, direct_vm, direct_charlie, body=bb, limit=ATTO, name="Second")
    assert out["rating"] == "BB"
    draw(c, direct_vm, direct_bob, MIN_DRAW)
    draw(c, direct_vm, direct_charlie, MIN_DRAW)
    advance(direct_vm, YEAR)
    i1 = int(c.get_borrower_schedule(k1)["accrued_interest"])
    i2 = int(c.get_borrower_schedule(k2)["accrued_interest"])
    assert i1 == MIN_DRAW * 400 // 10000 and i2 == MIN_DRAW * 1800 // 10000


def test_accrual_persists_across_second_drawdown(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, MIN_DRAW)
    advance(direct_vm, 30 * DAY)
    draw(c, direct_vm, direct_bob, MIN_DRAW)  # 1.0 GEN outstanding, still inside the 1.5 first tranche
    s = c.get_borrower_schedule(k)
    assert int(s["accrued_interest"]) == MIN_DRAW * 400 * 30 * DAY // (10000 * YEAR)


# ------------------------------------------------------------------- servicing
def test_payment_applies_interest_before_principal(c, direct_vm, direct_bob, line):
    advance(direct_vm, 60 * DAY)
    owed_interest = int(c.get_borrower_schedule(line)["accrued_interest"])
    out = repay(c, direct_vm, direct_bob, owed_interest + ATTO // 10)
    assert out["interest_paid"] == str(owed_interest) and out["principal_paid"] == str(ATTO // 10)


def test_small_payment_is_all_interest(c, direct_vm, direct_bob, line):
    advance(direct_vm, 60 * DAY)
    out = repay(c, direct_vm, direct_bob, 1000)
    assert out["interest_paid"] == "1000" and out["principal_paid"] == "0"


def test_full_repayment_clears_debt(c, direct_vm, direct_bob, line):
    advance(direct_vm, 30 * DAY)
    owed = int(c.get_borrower_schedule(line)["total_owed"])
    out = repay(c, direct_vm, direct_bob, owed)
    s = c.get_borrower_schedule(line)
    assert out["remaining"] == "0" and s["principal"] == "0" and s["repayment_due"] == 0
    assert c.get_pool_metrics()["borrowed_liquidity"] == "0"


def test_overpayment_refunded(c, direct_vm, direct_bob, line):
    owed = int(c.get_borrower_schedule(line)["total_owed"])
    out = repay(c, direct_vm, direct_bob, owed + 12345)
    assert out["refunded"] == "12345" and out["paid"] == str(owed)


def test_total_repaid_tracked(c, direct_vm, direct_bob, line):
    before = int(c.get_borrower_schedule(line)["total_repaid"])  # includes the staged first installment
    repay(c, direct_vm, direct_bob, ATTO // 2)
    repay(c, direct_vm, direct_bob, ATTO // 4)
    assert int(c.get_borrower_schedule(line)["total_repaid"]) == before + ATTO // 2 + ATTO // 4


def test_minimum_installment_extends_due_date(c, direct_vm, direct_bob, line):
    advance(direct_vm, 20 * DAY)
    mn = int(c.get_borrower_schedule(line)["minimum_payment"])
    repay(c, direct_vm, direct_bob, mn)
    due = c.get_borrower_schedule(line)["repayment_due"]
    assert due > c.get_credit_profile(line)["last_assessment_timestamp"] + 30 * DAY


def test_sub_minimum_payment_does_not_extend_due(c, direct_vm, direct_bob, line):
    before = c.get_borrower_schedule(line)["repayment_due"]
    advance(direct_vm, 5 * DAY)
    repay(c, direct_vm, direct_bob, 1000)
    assert c.get_borrower_schedule(line)["repayment_due"] == before


def test_service_without_debt_reverts(c, direct_vm, direct_bob):
    onboard(c, direct_vm, direct_bob)
    with direct_vm.expect_revert("no debt outstanding"):
        repay(c, direct_vm, direct_bob, 1)


def test_service_zero_value_reverts(c, direct_vm, direct_bob, line):
    with direct_vm.expect_revert("payment required"):
        repay(c, direct_vm, direct_bob, 0)


def test_service_by_stranger_reverts(c, direct_vm, direct_charlie, line):
    with direct_vm.expect_revert("no credit profile"):
        repay(c, direct_vm, direct_charlie, 1)


def test_repayment_restores_borrowing_capacity(c, direct_vm, direct_bob, line):
    repay(c, direct_vm, direct_bob, ATTO)
    draw(c, direct_vm, direct_bob, MIN_DRAW)  # owes 0.5 of the 1.5 first tranche -> may draw 0.5 again
    assert c.get_credit_profile(line)["borrowed_amount"] == str(LINE - ATTO + MIN_DRAW)


def test_amortisation_schedule_sums_to_principal(c, line):
    s = c.get_borrower_schedule(line)
    assert len(s["schedule"]) == 12
    assert sum(int(r["principal"]) for r in s["schedule"]) == LINE
    assert s["schedule"][-1]["balance"] == "0"


def test_amortisation_interest_declines(c, line):
    ints = [int(r["interest"]) for r in c.get_borrower_schedule(line)["schedule"]]
    assert ints == sorted(ints, reverse=True)


def test_cash_invariant_after_repayments(c, direct_vm, direct_bob, line):
    advance(direct_vm, 45 * DAY)
    out = repay(c, direct_vm, direct_bob, ATTO // 2)
    cash_in = 5 * ATTO + DEFAULT_BOND + int(out["paid"]) - LINE
    assert expected_balance(c) == cash_in


# ---------------------------------------------------------------------- closure
def test_close_returns_bond_after_repayment(c, direct_vm, direct_bob, line):
    owed = int(c.get_borrower_schedule(line)["total_owed"])
    repay(c, direct_vm, direct_bob, owed)
    send(direct_vm, direct_bob)
    assert c.close_credit_line() == str(DEFAULT_BOND)
    assert c.get_credit_profile(line)["status"] == "CLOSED" and c.get_pool_metrics()["bonds_held"] == "0"


def test_close_with_debt_reverts(c, direct_vm, direct_bob, line):
    send(direct_vm, direct_bob)
    with direct_vm.expect_revert("debt outstanding"):
        c.close_credit_line()


def test_closed_borrower_can_reapply(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    send(direct_vm, direct_bob)
    c.close_credit_line()
    apply(c, direct_vm, direct_bob)
    assert c.get_credit_profile(k)["status"] == "PENDING"


def test_close_pending_reverts(c, direct_vm, direct_bob):
    apply(c, direct_vm, direct_bob)
    send(direct_vm, direct_bob)
    with direct_vm.expect_revert("credit line is PENDING"):
        c.close_credit_line()


# ------------------------------------------------------------------ delinquency
def test_overdue_blocks_drawdown(c, direct_vm, direct_bob, line):
    advance(direct_vm, 31 * DAY)
    assert c.get_borrower_schedule(line)["overdue"] is True
    with direct_vm.expect_revert("repayment overdue"):
        draw(c, direct_vm, direct_bob, 1)


def test_overdue_not_yet_liquidatable_in_grace(c, direct_vm, direct_charlie, line):
    advance(direct_vm, 33 * DAY)
    assert c.get_borrower_schedule(line)["liquidatable"] is False
    send(direct_vm, direct_charlie)
    with direct_vm.expect_revert("within repayment grace"):
        c.liquidate_borrower(line)


def test_liquidate_without_debt_reverts(c, direct_vm, direct_bob, direct_charlie):
    k, _ = onboard(c, direct_vm, direct_bob)
    send(direct_vm, direct_charlie)
    with direct_vm.expect_revert("no debt"):
        c.liquidate_borrower(k)


def test_liquidate_pending_reverts(c, direct_vm, direct_bob, direct_charlie):
    apply(c, direct_vm, direct_bob)
    send(direct_vm, direct_charlie)
    with direct_vm.expect_revert("credit line is PENDING"):
        c.liquidate_borrower(key(c, direct_vm, direct_bob))


def test_insolvent_borrower_liquidated_after_grace(c, direct_vm, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    assert c.get_borrower_schedule(line)["liquidatable"] is True
    send(direct_vm, direct_charlie)
    out = c.liquidate_borrower(line)
    p = c.get_credit_profile(line)
    assert p["status"] == "DEFAULTED" and p["rating"] == "DEFAULT" and p["credit_limit"] == "0"
    assert out["principal"] == str(LINE)


def test_liquidation_seizes_bond_first(c, direct_vm, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    send(direct_vm, direct_charlie)
    out = c.liquidate_borrower(line)
    assert out["recovered_from_bond"] == str(DEFAULT_BOND)
    assert c.get_pool_metrics()["bonds_held"] == "0"


def test_liquidation_loss_waterfall_exact(c, direct_vm, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    send(direct_vm, direct_charlie)
    out = c.liquidate_borrower(line)
    m = c.get_pool_metrics()
    interest = LINE * 400 * 38 * DAY // (10000 * YEAR)
    reserve_cut = interest * 1000 // 10000
    loss = LINE - (DEFAULT_BOND - interest)  # bond covers interest first, then principal
    covered = min(reserve_cut, loss)  # the 10% interest cut seeds the reserve first
    assert int(out["insurance_covered"]) == covered
    assert int(out["lp_loss"]) == loss - covered
    assert int(m["total_deposited"]) == 5 * ATTO + (interest - reserve_cut) - (loss - covered)


def test_liquidation_insurance_absorbs_first(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    # an earlier slash seeds the reserve
    k0, o0 = onboard(c, direct_vm, direct_charlie, body=telemetry(monthly_revenue_usd=-1))
    k, _ = onboard(c, direct_vm, direct_bob, limit=ATTO)
    draw(c, direct_vm, direct_bob, MIN_DRAW)
    advance(direct_vm, 40 * DAY)
    send(direct_vm, direct_alice)
    out = c.liquidate_borrower(k)
    assert int(out["insurance_covered"]) > 0
    assert int(out["lp_loss"]) + int(out["insurance_covered"]) <= MIN_DRAW


def test_liquidation_preserves_cash_invariant(c, direct_vm, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    send(direct_vm, direct_charlie)
    c.liquidate_borrower(line)
    # cash held: deposits + bond - drawdown (nothing was repaid)
    assert expected_balance(c) == 5 * ATTO + DEFAULT_BOND - LINE
    m = c.get_pool_metrics()
    assert m["borrowed_liquidity"] == "0" and m["bonds_held"] == "0"


def test_default_rate_metric(c, direct_vm, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    send(direct_vm, direct_charlie)
    c.liquidate_borrower(line)
    m = c.get_pool_metrics()
    # the only loan defaulted; originated includes the staged tranche's installment round-trip
    assert m["default_rate_bps"] == int(m["cumulative_defaulted"]) * 10000 // int(m["cumulative_originated"]) > 9000


def test_default_rate_zero_without_defaults(c, line):
    assert c.get_pool_metrics()["default_rate_bps"] == 0


def test_defaulted_borrower_banned(c, direct_vm, direct_bob, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    send(direct_vm, direct_charlie)
    c.liquidate_borrower(line)
    send(direct_vm, direct_bob, bond_for(ATTO))
    with direct_vm.expect_revert("banned"):
        c.apply_for_credit("x", URL, ATTO)


def test_defaulted_cannot_draw_or_service(c, direct_vm, direct_bob, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    send(direct_vm, direct_charlie)
    c.liquidate_borrower(line)
    with direct_vm.expect_revert("DEFAULTED"):
        draw(c, direct_vm, direct_bob, 1)
    with direct_vm.expect_revert("DEFAULTED"):
        repay(c, direct_vm, direct_bob, 1)


def test_cannot_liquidate_twice(c, direct_vm, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    send(direct_vm, direct_charlie)
    c.liquidate_borrower(line)
    with direct_vm.expect_revert("DEFAULTED"):
        c.liquidate_borrower(line)


def test_lps_can_still_exit_after_default(c, direct_vm, direct_alice, direct_charlie, line):
    advance(direct_vm, 38 * DAY)
    send(direct_vm, direct_charlie)
    c.liquidate_borrower(line)
    send(direct_vm, direct_alice)
    assert int(c.withdraw_lp_capital(0)) < 5 * ATTO  # realised loss
