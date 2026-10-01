"""LP share accounting and interest-accrual invariants."""
import pytest
from conftest import *


@pytest.fixture
def pool(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    return c


def test_first_deposit_mints_one_to_one(direct_vm, pool, direct_alice):
    assert deposit(pool, direct_vm, direct_alice, 5 * ATTO) == str(5 * ATTO)
    m = pool.get_pool_metrics()
    assert m["total_deposited"] == str(5 * ATTO) and m["total_shares"] == str(5 * ATTO)


def test_deposit_below_minimum_reverts(direct_vm, pool, direct_alice):
    send(direct_vm, direct_alice, 10**14)
    with direct_vm.expect_revert("deposit below minimum"):
        pool.deposit_liquidity()


def test_zero_deposit_reverts(direct_vm, pool, direct_alice):
    send(direct_vm, direct_alice, 0)
    with direct_vm.expect_revert("deposit below minimum"):
        pool.deposit_liquidity()


def test_second_lp_proportional_at_par(direct_vm, pool, direct_alice, direct_bob):
    deposit(pool, direct_vm, direct_alice, 4 * ATTO)
    deposit(pool, direct_vm, direct_bob, 2 * ATTO)
    send(direct_vm, direct_bob)
    assert pool.get_lp_position(pool.whoami())["shares"] == str(2 * ATTO)


def test_position_view_reports_basis_and_value(direct_vm, pool, direct_alice):
    deposit(pool, direct_vm, direct_alice, 3 * ATTO)
    p = pool.get_lp_position(key(pool, direct_vm, direct_alice))
    assert p["value"] == p["cost_basis"] == str(3 * ATTO) and p["earned"] == "0"


def test_full_withdraw_clears_position(direct_vm, pool, direct_alice):
    deposit(pool, direct_vm, direct_alice, 3 * ATTO)
    send(direct_vm, direct_alice)
    assert pool.withdraw_lp_capital(0) == str(3 * ATTO)
    m = pool.get_pool_metrics()
    assert m["total_deposited"] == "0" and m["total_shares"] == "0"


def test_partial_withdraw_reduces_shares_and_basis(direct_vm, pool, direct_alice):
    deposit(pool, direct_vm, direct_alice, 4 * ATTO)
    send(direct_vm, direct_alice)
    pool.withdraw_lp_capital(ATTO)
    p = pool.get_lp_position(pool.whoami())
    assert p["shares"] == str(3 * ATTO) and p["cost_basis"] == str(3 * ATTO)


def test_withdraw_without_position_reverts(direct_vm, pool, direct_bob):
    send(direct_vm, direct_bob)
    with direct_vm.expect_revert("no LP position"):
        pool.withdraw_lp_capital(1)


def test_withdraw_more_than_value_reverts(direct_vm, pool, direct_alice):
    deposit(pool, direct_vm, direct_alice, ATTO)
    send(direct_vm, direct_alice)
    with direct_vm.expect_revert("exceeds position value"):
        pool.withdraw_lp_capital(2 * ATTO)


def test_negative_withdraw_reverts(direct_vm, pool, direct_alice):
    deposit(pool, direct_vm, direct_alice, ATTO)
    send(direct_vm, direct_alice)
    with direct_vm.expect_revert("negative amount"):
        pool.withdraw_lp_capital(-1)


def test_withdraw_blocked_by_lent_liquidity(direct_vm, pool, direct_alice, direct_bob):
    deposit(pool, direct_vm, direct_alice, 5 * ATTO)
    onboard(pool, direct_vm, direct_bob)
    draw(pool, direct_vm, direct_bob, 3 * ATTO)
    send(direct_vm, direct_alice)
    with direct_vm.expect_revert("insufficient pool liquidity"):
        pool.withdraw_lp_capital(4 * ATTO)
    assert pool.withdraw_lp_capital(0) == str(2 * ATTO)  # max available


def test_interest_raises_lp_value_not_shares(direct_vm, pool, direct_alice, direct_bob):
    deposit(pool, direct_vm, direct_alice, 5 * ATTO)
    onboard(pool, direct_vm, direct_bob)
    draw(pool, direct_vm, direct_bob, 2 * ATTO)
    advance(direct_vm, 90 * DAY)
    repay(pool, direct_vm, direct_bob, ATTO // 4)
    p = pool.get_lp_position(key(pool, direct_vm, direct_alice))
    assert p["shares"] == str(5 * ATTO) and int(p["earned"]) > 0


def test_interest_split_90_10(direct_vm, pool, direct_alice, direct_bob):
    deposit(pool, direct_vm, direct_alice, 5 * ATTO)
    onboard(pool, direct_vm, direct_bob)
    draw(pool, direct_vm, direct_bob, 2 * ATTO)
    advance(direct_vm, 30 * DAY)
    out = repay(pool, direct_vm, direct_bob, ATTO // 100)
    interest = int(out["interest_paid"])
    m = pool.get_pool_metrics()
    assert int(m["insurance_reserve"]) == interest * 1000 // 10000
    assert int(m["total_deposited"]) == 5 * ATTO + interest - int(m["insurance_reserve"])


def test_two_lps_share_yield_pro_rata(direct_vm, pool, direct_alice, direct_bob, direct_charlie):
    deposit(pool, direct_vm, direct_alice, 3 * ATTO)
    deposit(pool, direct_vm, direct_bob, 3 * ATTO)
    onboard(pool, direct_vm, direct_charlie)
    draw(pool, direct_vm, direct_charlie, ATTO)
    advance(direct_vm, 180 * DAY)
    repay(pool, direct_vm, direct_charlie, ATTO // 5)
    a = pool.get_lp_position(key(pool, direct_vm, direct_alice))
    b = pool.get_lp_position(key(pool, direct_vm, direct_bob))
    assert a["value"] == b["value"] and int(a["earned"]) > 0


def test_late_lp_does_not_capture_earlier_yield(direct_vm, pool, direct_alice, direct_bob, direct_charlie):
    deposit(pool, direct_vm, direct_alice, 4 * ATTO)
    onboard(pool, direct_vm, direct_charlie)
    draw(pool, direct_vm, direct_charlie, ATTO)
    advance(direct_vm, 120 * DAY)
    repay(pool, direct_vm, direct_charlie, ATTO // 5)
    deposit(pool, direct_vm, direct_bob, 4 * ATTO)
    b = pool.get_lp_position(key(pool, direct_vm, direct_bob))
    assert int(b["value"]) <= 4 * ATTO and int(b["earned"]) == 0
    a = pool.get_lp_position(key(pool, direct_vm, direct_alice))
    assert int(a["earned"]) > 0
    assert int(b["shares"]) < 4 * ATTO  # price per share > 1 after yield


def test_yield_index_is_monotonic(direct_vm, pool, direct_alice, direct_bob):
    deposit(pool, direct_vm, direct_alice, 5 * ATTO)
    onboard(pool, direct_vm, direct_bob)
    draw(pool, direct_vm, direct_bob, 2 * ATTO)
    seen = [int(pool.get_pool_metrics()["cumulative_yield_index"])]
    for _ in range(4):
        advance(direct_vm, 30 * DAY)
        repay(pool, direct_vm, direct_bob, ATTO // 10)
        seen.append(int(pool.get_pool_metrics()["cumulative_yield_index"]))
    assert seen == sorted(seen) and seen[-1] > seen[0]


def test_withdrawal_after_yield_exceeds_deposit(direct_vm, pool, direct_alice, direct_bob):
    deposit(pool, direct_vm, direct_alice, 5 * ATTO)
    onboard(pool, direct_vm, direct_bob)
    draw(pool, direct_vm, direct_bob, 2 * ATTO)
    advance(direct_vm, 365 * DAY)
    repay(pool, direct_vm, direct_bob, ATTO // 2)
    repay(pool, direct_vm, direct_bob, int(pool.get_borrower_schedule(key(pool, direct_vm, direct_bob))["total_owed"]))
    send(direct_vm, direct_alice)
    assert int(pool.withdraw_lp_capital(0)) > 5 * ATTO


def test_sum_of_lp_values_never_exceeds_assets(direct_vm, pool, direct_alice, direct_bob, direct_charlie):
    deposit(pool, direct_vm, direct_alice, 3 * ATTO + 7)
    deposit(pool, direct_vm, direct_bob, 2 * ATTO + 13)
    onboard(pool, direct_vm, direct_charlie)
    draw(pool, direct_vm, direct_charlie, ATTO)
    advance(direct_vm, 77 * DAY)
    repay(pool, direct_vm, direct_charlie, ATTO // 7)
    total = sum(int(pool.get_lp_position(key(pool, direct_vm, w))["value"]) for w in (direct_alice, direct_bob))
    assert total <= int(pool.get_pool_metrics()["total_deposited"])
    assert int(pool.get_pool_metrics()["total_deposited"]) - total < 10


def test_cash_invariant_through_lifecycle(direct_vm, pool, direct_alice, direct_bob):
    deposit(pool, direct_vm, direct_alice, 5 * ATTO)
    onboard(pool, direct_vm, direct_bob)
    draw(pool, direct_vm, direct_bob, 2 * ATTO)
    advance(direct_vm, 60 * DAY)
    out = repay(pool, direct_vm, direct_bob, ATTO // 3)
    m = pool.get_pool_metrics()
    # cash in = LP deposits + bond + repayments - drawdown
    cash_in = 5 * ATTO + DEFAULT_BOND + int(out["paid"]) - 2 * ATTO
    assert expected_balance(pool) == cash_in
