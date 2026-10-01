"""Governance controls, access control and view surface."""
import pytest
from conftest import *


@pytest.fixture
def gov(direct_vm, direct_deploy, direct_owner):
    direct_vm.sender = direct_owner
    c = direct_deploy(CONTRACT)
    direct_vm.sender = direct_owner
    return c


def test_governor_is_deployer(gov, direct_vm, direct_owner):
    gov.set_usd_per_gen(300_000)
    assert gov.get_pool_metrics()["usd_per_gen"] == 300_000


def test_non_governor_cannot_set_rate(gov, direct_vm, direct_bob):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("governor only"):
        gov.set_usd_per_gen(300_000)


@pytest.mark.parametrize("v", [0, 999, 10_000_001])
def test_usd_per_gen_bounds(gov, direct_vm, direct_owner, v):
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("out of bounds"):
        gov.set_usd_per_gen(v)


def test_usd_per_gen_reprices_the_request(gov, direct_vm, direct_owner, direct_alice, direct_bob):
    """A pricier GEN makes the same GEN request a bigger USD debt: DSCR falls
    and the rating steps down, shrinking the limit."""
    deposit(gov, direct_vm, direct_alice, 5 * ATTO)
    k, base = onboard(gov, direct_vm, direct_bob, limit=5 * ATTO // 2)
    assert base["rating"] == "AAA"
    feed(direct_vm, telemetry())
    direct_vm.sender = direct_owner
    gov.set_usd_per_gen(500_000)
    out = assess(gov, direct_vm, k, caller=direct_bob)  # debt-free line may be re-rated
    assert out["rating"] == "AA"
    assert int(out["credit_limit"]) == 2_500_008 * 3500 // 10000 * ATTO // 500_000


def test_freeze_blocks_drawdown_allows_repayment(gov, direct_vm, direct_owner, direct_alice, direct_bob):
    deposit(gov, direct_vm, direct_alice, 5 * ATTO)
    k, _ = onboard(gov, direct_vm, direct_bob)
    draw(gov, direct_vm, direct_bob, ATTO)
    direct_vm.sender = direct_owner
    gov.freeze_borrower(k)
    assert gov.get_credit_profile(k)["status"] == "FROZEN"
    with direct_vm.expect_revert("FROZEN"):
        draw(gov, direct_vm, direct_bob, 1)
    repay(gov, direct_vm, direct_bob, ATTO // 4)  # still allowed


def test_unfreeze_restores_line(gov, direct_vm, direct_owner, direct_alice, direct_bob):
    deposit(gov, direct_vm, direct_alice, 5 * ATTO)
    k, _ = onboard(gov, direct_vm, direct_bob)
    direct_vm.sender = direct_owner
    gov.freeze_borrower(k)
    gov.unfreeze_borrower(k)
    draw(gov, direct_vm, direct_bob, ATTO)


def test_freeze_requires_governor(gov, direct_vm, direct_alice, direct_bob):
    deposit(gov, direct_vm, direct_alice, 5 * ATTO)
    k, _ = onboard(gov, direct_vm, direct_bob)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("governor only"):
        gov.freeze_borrower(k)


def test_freeze_pending_rejected(gov, direct_vm, direct_owner, direct_bob):
    apply(gov, direct_vm, direct_bob)
    k = key(gov, direct_vm, direct_bob)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("not active"):
        gov.freeze_borrower(k)


def test_unfreeze_active_rejected(gov, direct_vm, direct_owner, direct_alice, direct_bob):
    deposit(gov, direct_vm, direct_alice, 5 * ATTO)
    k, _ = onboard(gov, direct_vm, direct_bob)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("not frozen"):
        gov.unfreeze_borrower(k)


def test_frozen_defaulted_flow_liquidatable(gov, direct_vm, direct_owner, direct_alice, direct_bob):
    deposit(gov, direct_vm, direct_alice, 5 * ATTO)
    k, _ = onboard(gov, direct_vm, direct_bob)
    draw(gov, direct_vm, direct_bob, ATTO)
    direct_vm.sender = direct_owner
    gov.freeze_borrower(k)
    advance(direct_vm, 40 * DAY)
    gov.liquidate_borrower(k)
    assert gov.get_credit_profile(k)["status"] == "DEFAULTED"


def test_transfer_governor(gov, direct_vm, direct_owner, direct_bob):
    new = key(gov, direct_vm, direct_bob)
    direct_vm.sender = direct_owner
    gov.transfer_governor(new)
    with direct_vm.expect_revert("governor only"):
        gov.set_usd_per_gen(300_000)
    direct_vm.sender = direct_bob
    gov.set_usd_per_gen(300_000)


def test_transfer_governor_requires_governor(gov, direct_vm, direct_bob):
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("governor only"):
        gov.transfer_governor(key(gov, direct_vm, direct_bob))


# ------------------------------------------------------------------------ views
def test_empty_pool_metrics(gov):
    m = gov.get_pool_metrics()
    assert m["total_deposited"] == "0" and m["utilization_bps"] == 0 and m["lp_apy_bps"] == 0
    assert m["default_rate_bps"] == 0 and m["borrower_count"] == 0


def test_whoami_matches_profile_key(gov, direct_vm, direct_bob):
    apply(gov, direct_vm, direct_bob)
    k = key(gov, direct_vm, direct_bob)
    assert gov.get_credit_profile(k)["borrower"] == k


def test_lp_view_for_unknown_address_is_empty(gov, direct_vm, direct_charlie):
    p = gov.get_lp_position(key(gov, direct_vm, direct_charlie))
    assert p["shares"] == "0" and p["value"] == "0"


def test_schedule_for_pending_is_empty(gov, direct_vm, direct_bob):
    apply(gov, direct_vm, direct_bob)
    s = gov.get_borrower_schedule(key(gov, direct_vm, direct_bob))
    assert s["principal"] == "0" and s["schedule"] == [] and s["overdue"] is False


def test_schedule_unknown_borrower_reverts(gov, direct_vm, direct_bob):
    with direct_vm.expect_revert("unknown borrower"):
        gov.get_borrower_schedule(key(gov, direct_vm, direct_bob))


def test_three_entity_registry(gov, direct_vm, direct_alice, direct_bob, direct_charlie, direct_owner):
    deposit(gov, direct_vm, direct_alice, 5 * ATTO)
    onboard(gov, direct_vm, direct_bob)
    onboard(gov, direct_vm, direct_charlie, body=hyperscale(), limit=ATTO, name="HyperScale Labs")
    apply(gov, direct_vm, direct_owner, name="ZeroProof Systems")
    states = [gov.get_credit_profile(gov.get_borrower_at(i)) for i in range(3)]
    assert [(s["rating"], s["status"]) for s in states] == [("AAA", "ACTIVE"), ("C", "ACTIVE"), ("UNRATED", "PENDING")]
