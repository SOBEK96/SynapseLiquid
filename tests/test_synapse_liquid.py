"""Audit regression PoCs: each test replays a finding from the security review
and asserts the exploit no longer works."""
import pytest
from conftest import *


@pytest.fixture
def c(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    deposit(c, direct_vm, direct_alice, 5 * ATTO)
    return c


# ------------------------------------------------ FINDING 1: identity binding
def test_foreign_telemetry_replay_rejected(c, direct_vm, direct_bob, direct_charlie):
    """PoC: attacker applies with a URL serving the victim's public, AAA telemetry."""
    victim = key(c, direct_vm, direct_bob)
    feed(direct_vm, telemetry(borrower_address=victim)); review(direct_vm)
    apply(c, direct_vm, direct_charlie)  # attacker, same public URL
    atk = key(c, direct_vm, direct_charlie)
    with direct_vm.expect_revert("ERR_BORROWER_MISMATCH"):
        assess(c, direct_vm, atk)
    p = c.get_credit_profile(atk)
    assert p["status"] == "PENDING" and p["rating"] == "UNRATED" and p["credit_limit"] == "0"
    with direct_vm.expect_revert("credit line is PENDING"):
        draw(c, direct_vm, direct_charlie, 1)
    assert c.get_pool_metrics()["borrowed_liquidity"] == "0"


def test_victim_can_still_use_own_telemetry(c, direct_vm, direct_bob):
    victim = key(c, direct_vm, direct_bob)
    feed(direct_vm, telemetry(borrower_address=victim)); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    assert assess(c, direct_vm, victim)["rating"] == "AAA"


def test_binding_is_case_insensitive(c, direct_vm, direct_bob):
    victim = key(c, direct_vm, direct_bob)
    feed(direct_vm, telemetry(borrower_address=victim.lower())); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    assert assess(c, direct_vm, victim)["status"] == "ACTIVE"
    k2 = key(c, direct_vm, direct_bob)
    assert k2 == victim


@pytest.mark.parametrize("bound", ["", "0x0000000000000000000000000000000000000001", "not-an-address", 12345, None])
def test_missing_or_wrong_borrower_address_rejected(c, direct_vm, direct_bob, bound):
    feed(direct_vm, {**telemetry(), "borrower_address": bound}); review(direct_vm)
    apply(c, direct_vm, direct_bob)
    with direct_vm.expect_revert("ERR_BORROWER_MISMATCH"):
        assess(c, direct_vm, key(c, direct_vm, direct_bob))


def test_mismatch_rejects_before_fraud_check(c, direct_vm, direct_bob, direct_charlie):
    """A foreign *fraudulent* file must not slash the victim-bound applicant either."""
    victim = key(c, direct_vm, direct_bob)
    feed(direct_vm, telemetry(borrower_address=victim, monthly_revenue_usd=-1)); review(direct_vm)
    apply(c, direct_vm, direct_charlie)
    with direct_vm.expect_revert("ERR_BORROWER_MISMATCH"):
        assess(c, direct_vm, key(c, direct_vm, direct_charlie))
    assert c.get_pool_metrics()["cumulative_slashed"] == "0"


def test_mismatch_does_not_strand_the_bond(c, direct_vm, direct_charlie):
    feed(direct_vm, telemetry(borrower_address="0x0000000000000000000000000000000000000001")); review(direct_vm)
    apply(c, direct_vm, direct_charlie)
    with direct_vm.expect_revert("ERR_BORROWER_MISMATCH"):
        assess(c, direct_vm, key(c, direct_vm, direct_charlie))
    send(direct_vm, direct_charlie)
    assert c.cancel_application() == str(DEFAULT_BOND)
    assert c.get_pool_metrics()["bonds_held"] == "0"


def test_cancel_requires_pending_application(c, direct_vm, direct_bob):
    send(direct_vm, direct_bob)
    with direct_vm.expect_revert("no pending application"):
        c.cancel_application()
    onboard(c, direct_vm, direct_bob)
    with direct_vm.expect_revert("no pending application"):
        c.cancel_application()


# ------------------------------------------------ FINDING 2: global utilisation cap
def test_global_utilization_cap_enforced(c, direct_vm, direct_bob, direct_charlie, direct_owner):
    """PoC: three borrowers, each inside its own limit and first tranche, together
    try to pass 60% of the pool."""
    onboard(c, direct_vm, direct_bob, limit=3 * ATTO, name="B")
    onboard(c, direct_vm, direct_charlie, limit=3 * ATTO, name="C")
    onboard(c, direct_vm, direct_owner, limit=3 * ATTO, name="O")
    draw(c, direct_vm, direct_bob, LINE)
    draw(c, direct_vm, direct_charlie, ATTO)                  # 2.5 of 5 GEN
    with direct_vm.expect_revert("ERR_POOL_CAP_REACHED"):
        draw(c, direct_vm, direct_owner, 6 * ATTO // 10)      # 3.1 / 5 > 60%
    draw(c, direct_vm, direct_owner, ATTO // 2)               # exactly 3.0 / 5 == 60%
    assert c.get_pool_metrics()["utilization_bps"] == MAX_UTIL_BPS
    with direct_vm.expect_revert("ERR_POOL_CAP_REACHED"):
        draw(c, direct_vm, direct_charlie, ATTO // 2)         # inside charlie's own tranche, still refused


def test_sybil_swarm_cannot_pass_the_cap(c, direct_vm, direct_bob, direct_charlie, direct_owner, direct_alice):
    for who, name in ((direct_bob, "S1"), (direct_charlie, "S2"), (direct_owner, "S3")):
        onboard(c, direct_vm, who, limit=2 * ATTO, name=name)
        draw(c, direct_vm, who, ATTO)                         # 50% of each 2 GEN line
    onboard(c, direct_vm, direct_alice, limit=2 * ATTO, name="S4")
    with direct_vm.expect_revert("ERR_POOL_CAP_REACHED"):     # 3 / 5 already == 60%
        draw(c, direct_vm, direct_alice, MIN_DRAW)
    assert int(c.get_pool_metrics()["borrowed_liquidity"]) <= 3 * ATTO


def test_cap_binds_even_when_own_limit_is_larger(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, limit=4 * ATTO)
    assert int(out["credit_limit"]) <= 3 * ATTO  # concentration cap at assessment
    with direct_vm.expect_revert("exceeds credit limit"):
        draw(c, direct_vm, direct_bob, 3 * ATTO + 1)


def test_repayment_frees_cap_headroom(c, direct_vm, direct_bob, direct_charlie, direct_owner):
    onboard(c, direct_vm, direct_bob, limit=3 * ATTO, name="B")
    onboard(c, direct_vm, direct_charlie, limit=3 * ATTO, name="C")
    onboard(c, direct_vm, direct_owner, limit=ATTO, name="O")
    draw(c, direct_vm, direct_bob, LINE)
    draw(c, direct_vm, direct_charlie, LINE)                  # 3.0 / 5 == cap
    with direct_vm.expect_revert("ERR_POOL_CAP_REACHED"):
        draw(c, direct_vm, direct_owner, MIN_DRAW)
    repay(c, direct_vm, direct_bob, ATTO)
    draw(c, direct_vm, direct_owner, MIN_DRAW)


# ------------------------------------------------ FINDING 3: bad-debt haircut
def _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    deposit(c, direct_vm, direct_bob, 2 * ATTO)  # alice 5 + bob 2 = 7 GEN; cap 4.2
    onboard(c, direct_vm, direct_charlie, limit=3 * ATTO)
    draw(c, direct_vm, direct_charlie, LINE)


def test_delinquent_loan_bad_debt_haircut(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    """PoC: once a loan is overdue the early LP could withdraw at par and leave
    the loss to the last LP. Now the loss is marked to market for everyone."""
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    before = int(c.get_lp_position(key(c, direct_vm, direct_alice))["value"])
    assert before == 5 * ATTO
    advance(direct_vm, 31 * DAY)  # past the due date, before liquidation is allowed
    m = c.get_pool_metrics()
    nav = 7 * ATTO - LINE
    assert m["delinquent_principal"] == str(LINE) and c.get_total_assets() == str(nav)
    a = c.get_lp_position(key(c, direct_vm, direct_alice))
    b = c.get_lp_position(key(c, direct_vm, direct_bob))
    assert int(a["value"]) == 5 * ATTO * nav // (7 * ATTO) and int(b["value"]) == 2 * ATTO * nav // (7 * ATTO)
    # both holders are marked down by the same fraction
    assert int(a["value"]) * 2 * ATTO == pytest.approx(int(b["value"]) * 5 * ATTO, rel=1e-9)


def test_early_exit_cannot_dump_loss_on_late_lp(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    advance(direct_vm, 31 * DAY)
    send(direct_vm, direct_alice)
    got_a = int(c.withdraw_lp_capital(0))
    assert got_a < 5 * ATTO                       # not par
    ratio_a = got_a / (5 * ATTO)
    send(direct_vm, direct_bob)
    got_b = int(c.withdraw_lp_capital(0))
    ratio_b = got_b / (2 * ATTO)
    assert ratio_a == pytest.approx((7 * ATTO - LINE) / (7 * ATTO), rel=1e-6)
    assert ratio_b == pytest.approx(ratio_a, rel=1e-6)  # identical recovery: no first-mover advantage


def test_withdrawal_is_capped_by_haircut_value(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    advance(direct_vm, 31 * DAY)
    send(direct_vm, direct_alice)
    with direct_vm.expect_revert("exceeds position value"):
        c.withdraw_lp_capital(5 * ATTO * (7 * ATTO - LINE) // (7 * ATTO) + 10**12)


def test_deposits_blocked_while_book_is_marked_down(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    advance(direct_vm, 31 * DAY)
    send(direct_vm, direct_alice, ATTO)
    with direct_vm.expect_revert("ERR_POOL_DELINQUENT"):
        c.deposit_liquidity()


def test_curing_the_loan_restores_share_price(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    advance(direct_vm, 31 * DAY)
    owed = int(c.get_borrower_schedule(key(c, direct_vm, direct_charlie))["total_owed"])
    repay(c, direct_vm, direct_charlie, owed)
    assert c.get_pool_metrics()["delinquent_principal"] == "0"
    assert int(c.get_lp_position(key(c, direct_vm, direct_alice))["value"]) >= 5 * ATTO


def test_liquidation_realises_the_markdown(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    advance(direct_vm, 40 * DAY)
    send(direct_vm, direct_alice)
    c.liquidate_borrower(key(c, direct_vm, direct_charlie))
    m = c.get_pool_metrics()
    assert m["delinquent_principal"] == "0"
    assert int(m["lp_nav"]) < 7 * ATTO  # loss now booked in total_assets
    assert m["lp_nav"] == m["total_deposited"]


def test_performing_loans_are_not_haircut(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    advance(direct_vm, 20 * DAY)
    assert c.get_pool_metrics()["delinquent_principal"] == "0"
    assert c.get_total_assets() == str(7 * ATTO)


# ------------------------------------------------ FINDING 4a: proportional bond
def test_proportional_bond_scaling(c, direct_vm, direct_bob, direct_charlie):
    assert bond_for(ATTO // 2) == BOND                       # floor: 15% of 0.5 = 0.075 < 0.1
    assert bond_for(2 * ATTO) == 3 * ATTO // 10              # 15% of 2 GEN
    assert bond_for(10 * ATTO) == 3 * ATTO // 2
    apply(c, direct_vm, direct_bob, limit=2 * ATTO)
    p = c.get_credit_profile(key(c, direct_vm, direct_bob))
    assert p["underwriting_bond"] == str(3 * ATTO // 10)
    apply(c, direct_vm, direct_charlie, limit=ATTO // 2)
    assert c.get_credit_profile(key(c, direct_vm, direct_charlie))["underwriting_bond"] == str(BOND)
    assert c.get_pool_metrics()["bonds_held"] == str(3 * ATTO // 10 + BOND)


def test_flat_bond_no_longer_accepted_for_large_limits(c, direct_vm, direct_bob):
    send(direct_vm, direct_bob, BOND)
    with direct_vm.expect_revert("exact underwriting bond required"):
        c.apply_for_credit("Co", URL, 3 * ATTO)


def test_overpaying_the_bond_is_rejected(c, direct_vm, direct_bob):
    send(direct_vm, direct_bob, 2 * bond_for(ATTO))
    with direct_vm.expect_revert("exact underwriting bond required"):
        c.apply_for_credit("Co", URL, ATTO)


def test_bond_covers_at_least_fifteen_percent_of_the_line(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, limit=3 * ATTO)
    p = c.get_credit_profile(k)
    assert int(p["underwriting_bond"]) * 100 >= int(p["credit_limit"]) * 15


def test_larger_bond_is_seized_on_default(c, direct_vm, direct_bob, direct_charlie):
    k, _ = onboard(c, direct_vm, direct_bob, limit=3 * ATTO)
    draw(c, direct_vm, direct_bob, LINE)
    advance(direct_vm, 40 * DAY)
    send(direct_vm, direct_charlie)
    out = c.liquidate_borrower(k)
    assert out["recovered_from_bond"] == str(DEFAULT_BOND)
    assert int(out["lp_loss"]) < 3 * ATTO - DEFAULT_BOND + ATTO // 10


# ------------------------------------------------ FINDING 4b: absolute maturity
def test_absolute_maturity_enforced(c, direct_vm, direct_bob):
    """PoC: roll the due date forward forever. The due date is clamped to the
    terminal maturity and the minimum instalment amortises toward it."""
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, LINE)
    expiry = c.get_borrower_schedule(k)["loan_expiry"]
    start = c.get_credit_profile(k)["last_assessment_timestamp"]
    assert expiry == start + (COOLDOWN + 1) + 365 * DAY  # fixed at the first drawdown
    for _ in range(14):
        advance(direct_vm, 29 * DAY)
        s = c.get_borrower_schedule(k)
        if s["principal"] == "0":
            break
        repay(c, direct_vm, direct_bob, int(s["minimum_payment"]))
        assert c.get_borrower_schedule(k)["repayment_due"] <= expiry
    s = c.get_borrower_schedule(k)
    assert s["principal"] == "0" and s["loan_expiry"] == 0  # fully amortised by maturity


def test_final_instalment_is_the_whole_balance(c, direct_vm, direct_bob):
    """In the last period the minimum instalment equals everything owed, so
    there is nothing left to roll over past the terminal date."""
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, LINE)
    advance(direct_vm, 340 * DAY)
    s = c.get_borrower_schedule(k)
    assert s["months_left"] == 1 and s["minimum_payment"] == s["total_owed"]
    repay(c, direct_vm, direct_bob, int(s["minimum_payment"]))
    assert c.get_borrower_schedule(k)["principal"] == "0"


def test_matured_loan_is_delinquent_and_liquidatable(c, direct_vm, direct_bob, direct_charlie):
    """Pay the schedule for 11 months, then stall: the due date cannot roll on,
    and the loan is delinquent at maturity however much was repaid before."""
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, LINE)
    expiry = c.get_borrower_schedule(k)["loan_expiry"]
    for _ in range(11):
        advance(direct_vm, 29 * DAY)
        repay(c, direct_vm, direct_bob, int(c.get_borrower_schedule(k)["minimum_payment"]))
        assert c.get_borrower_schedule(k)["repayment_due"] <= expiry
    advance(direct_vm, 29 * DAY)
    repay(c, direct_vm, direct_bob, 1000)  # sub-minimum: does not extend the due date
    assert c.get_borrower_schedule(k)["repayment_due"] <= expiry
    advance(direct_vm, 32 * DAY)  # past maturity and the 7-day grace
    s = c.get_borrower_schedule(k)
    assert s["overdue"] and s["liquidatable"]
    with direct_vm.expect_revert():
        draw(c, direct_vm, direct_bob, 1)
    send(direct_vm, direct_charlie)
    assert c.liquidate_borrower(k)["principal"] != "0"


def test_topup_drawdown_does_not_extend_maturity(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, ATTO)
    expiry = c.get_borrower_schedule(k)["loan_expiry"]
    advance(direct_vm, 20 * DAY)
    draw(c, direct_vm, direct_bob, ATTO // 2)  # 1.5 == the first tranche
    assert c.get_borrower_schedule(k)["loan_expiry"] == expiry


def test_minimum_instalment_scales_with_time_left(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, LINE)
    early = c.get_borrower_schedule(k)
    advance(direct_vm, 300 * DAY)
    late = c.get_borrower_schedule(k)
    assert late["months_left"] < early["months_left"]
    assert int(late["minimum_payment"]) - int(late["accrued_interest"]) > LINE // 12


def test_full_repayment_clears_maturity_for_a_fresh_cycle(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, ATTO)
    repay(c, direct_vm, direct_bob, int(c.get_borrower_schedule(k)["total_owed"]))
    assert c.get_borrower_schedule(k)["loan_expiry"] == 0
    advance(direct_vm, 5 * DAY)
    draw(c, direct_vm, direct_bob, ATTO)
    assert c.get_borrower_schedule(k)["loan_expiry"] > 0


# ------------------------------------------------ FINDING 4c: URL sanitisation
@pytest.mark.parametrize("uri", [
    "https://10.0.0.1/t.json", "https://10.255.255.254/t.json",
    "https://172.16.0.1/t.json", "https://172.31.255.255/t.json",
    "https://192.168.0.10/t.json", "https://192.168.255.1/t.json",
    "https://169.254.169.254/latest/meta-data/", "https://169.254.170.2/v2/credentials",
    "https://127.0.0.1/t.json", "https://127.1/t.json", "https://0.0.0.0/t.json",
    "https://0x7f.0.0.1/t.json", "https://2130706433/t.json", "https://0177.0.0.1/t.json",
    "https://[::1]/t.json", "https://[fd00::1]/t.json",
    "https://localhost/t.json", "https://LOCALHOST./t.json", "https://app.localhost/t.json",
    "https://metadata.google.internal/computeMetadata/v1/", "https://svc.internal/t.json",
    "https://printer.local/t.json", "https://10.0.0.1.nip.io/t.json", "https://a.sslip.io/t.json",
    "https://user:pw@example.com/t.json", "https://169.254.169.254@example.com/t.json",
    "http://example.com/t.json", "ftp://example.com/t.json", "//example.com/t.json", "https://nodots/t.json",
])
def test_ssrf_hosts_rejected(c, direct_vm, direct_bob, uri):
    send(direct_vm, direct_bob, bond_for(ATTO))
    with direct_vm.expect_revert("public https URL"):
        c.apply_for_credit("Co", uri, ATTO)


@pytest.mark.parametrize("uri", [
    "https://example.com/t.json", "https://telemetry.aether.io/v1/proof.json",
    "https://raw.githubusercontent.com/o/r/main/telemetry/aether.json",
    "https://gist.githubusercontent.com/o/abc/raw/aether.json",
])
def test_public_https_hosts_accepted(c, direct_vm, direct_bob, uri):
    apply(c, direct_vm, direct_bob, uri=uri, limit=ATTO)
    assert c.get_credit_profile(key(c, direct_vm, direct_bob))["metadata_uri"] == uri


# ============ FINAL AUDIT: active-borrower registry (gas-loop removal) ============
def test_registry_counts_only_indebted_borrowers(c, direct_vm, direct_bob, direct_charlie, direct_owner):
    for who, name in ((direct_bob, "A"), (direct_charlie, "B"), (direct_owner, "C")):
        onboard(c, direct_vm, who, limit=ATTO, name=name)
    m = c.get_pool_metrics()
    assert m["borrower_count"] == 3 and m["active_borrowers"] == 0  # rated, but nobody has drawn
    draw(c, direct_vm, direct_bob, ATTO // 2)
    assert c.get_pool_metrics()["active_borrowers"] == 1


def test_cancelled_and_pending_applications_never_enter_the_loop(c, direct_vm, direct_alice):
    for i in range(1, 12):  # a swarm of spam applications, some cancelled
        who = bytes([i]) * 20
        feed(direct_vm, telemetry()); review(direct_vm)
        apply(c, direct_vm, who, limit=ATTO)
        if i % 2:
            send(direct_vm, who)
            c.cancel_application()
    m = c.get_pool_metrics()
    assert m["borrower_count"] == 11 and m["active_borrowers"] == 0
    assert c.get_total_assets() == str(5 * ATTO)  # NAV path touches zero of them


def test_registry_swap_remove_keeps_nav_correct(c, direct_vm, direct_bob, direct_charlie, direct_owner):
    for who, name in ((direct_bob, "A"), (direct_charlie, "B"), (direct_owner, "C")):
        onboard(c, direct_vm, who, limit=ATTO, name=name)
        draw(c, direct_vm, who, ATTO // 2)
    assert c.get_pool_metrics()["active_borrowers"] == 3
    # the MIDDLE borrower repays in full -> swap-remove moves the last into its slot
    owed = int(c.get_borrower_schedule(key(c, direct_vm, direct_charlie))["total_owed"])
    repay(c, direct_vm, direct_charlie, owed)
    assert c.get_pool_metrics()["active_borrowers"] == 2
    advance(direct_vm, 40 * DAY)
    # the two remaining loans are overdue and both still counted exactly once
    assert c.get_pool_metrics()["delinquent_principal"] == str(ATTO)
    assert int(c.get_total_assets()) == int(c.get_pool_metrics()["total_deposited"]) - ATTO  # nominal less marked-down
    repay(c, direct_vm, direct_owner, int(c.get_borrower_schedule(key(c, direct_vm, direct_owner))["total_owed"]))
    assert c.get_pool_metrics()["delinquent_principal"] == str(ATTO // 2)


def test_registry_entry_removed_on_liquidation_and_reused(c, direct_vm, direct_bob, direct_charlie):
    k, _ = onboard(c, direct_vm, direct_bob, limit=ATTO)
    draw(c, direct_vm, direct_bob, ATTO // 2)
    advance(direct_vm, 40 * DAY)
    send(direct_vm, direct_charlie)
    c.liquidate_borrower(k)
    assert c.get_pool_metrics()["active_borrowers"] == 0
    advance(direct_vm, 4 * DAY)  # clear any liquidation pause
    onboard(c, direct_vm, direct_charlie, limit=ATTO, name="Next")
    draw(c, direct_vm, direct_charlie, ATTO // 2)
    assert c.get_pool_metrics()["active_borrowers"] == 1


def test_active_borrower_set_is_hard_bounded(direct_vm, direct_deploy, direct_alice):
    """The NAV loop is bounded: the 65th simultaneous borrower is refused."""
    c = direct_deploy(CONTRACT)
    deposit(c, direct_vm, direct_alice, 200 * ATTO)
    who = [bytes([i + 1]) * 20 for i in range(65)]
    for i, w in enumerate(who):
        onboard(c, direct_vm, w, limit=ATTO, name=f"Co{i}", cooldown=False)
    advance(direct_vm, COOLDOWN + 1)
    for w in who[:64]:
        draw_raw(c, direct_vm, w, MIN_DRAW)
    assert c.get_pool_metrics()["active_borrowers"] == 64
    with direct_vm.expect_revert("ERR_ACTIVE_BORROWER_CAP"):
        draw_raw(c, direct_vm, who[64], MIN_DRAW)
    # a borrower who repays in full is evicted at once and frees the slot...
    repay(c, direct_vm, who[0], int(c.get_borrower_schedule(key(c, direct_vm, who[0]))["total_owed"]))
    assert c.get_pool_metrics()["active_borrowers"] == 63
    draw_raw(c, direct_vm, who[64], MIN_DRAW)
    assert c.get_pool_metrics()["active_borrowers"] == 64
    # ...and the evicted borrower cannot sneak back past the bound (stale-slot regression)
    with direct_vm.expect_revert("ERR_ACTIVE_BORROWER_CAP"):
        draw_raw(c, direct_vm, who[0], MIN_DRAW)


# ============ FINAL AUDIT: 24h cooldown between assessment and first drawdown ============
def test_cooldown_blocks_immediate_drawdown(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob, cooldown=False)
    with direct_vm.expect_revert("ERR_COOLDOWN_ACTIVE"):
        draw_raw(c, direct_vm, direct_bob, MIN_DRAW)
    advance(direct_vm, COOLDOWN - 60)
    with direct_vm.expect_revert("ERR_COOLDOWN_ACTIVE"):
        draw_raw(c, direct_vm, direct_bob, MIN_DRAW)
    advance(direct_vm, 61)
    draw_raw(c, direct_vm, direct_bob, MIN_DRAW)


def test_profile_reports_when_drawdown_opens(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob, cooldown=False)
    p = c.get_credit_profile(k)
    assert p["drawdown_available_at"] == p["last_assessment_timestamp"] + COOLDOWN


def test_reassessment_restarts_the_cooldown(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)  # cooldown already elapsed
    feed(direct_vm, telemetry())
    assess(c, direct_vm, k)  # fresh consensus before any drawdown
    with direct_vm.expect_revert("ERR_COOLDOWN_ACTIVE"):
        draw_raw(c, direct_vm, direct_bob, MIN_DRAW)


def test_cooldown_is_for_the_initial_drawdown_only(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, ATTO)
    repay(c, direct_vm, direct_bob, int(c.get_borrower_schedule(k)["total_owed"]))
    draw_raw(c, direct_vm, direct_bob, ATTO)  # immediately again: no cooldown, history exists


# ============ FINAL AUDIT: first-tranche cap / healthy performance ============
def test_first_tranche_capped_at_half_the_limit(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob)
    half = int(out["credit_limit"]) // 2
    assert c.get_credit_profile(k)["first_tranche_cap"] == str(half)
    with direct_vm.expect_revert("ERR_TRANCHE_CAP"):
        draw_raw(c, direct_vm, direct_bob, half + 1)
    with direct_vm.expect_revert("ERR_TRANCHE_CAP"):
        draw_raw(c, direct_vm, direct_bob, int(out["credit_limit"]))  # 100% in one tx
    draw_raw(c, direct_vm, direct_bob, half)


def test_second_tranche_requires_a_paid_installment(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob)
    limit = int(out["credit_limit"])
    draw_raw(c, direct_vm, direct_bob, limit // 2)
    with direct_vm.expect_revert("ERR_TRANCHE_CAP"):  # two small draws cannot dodge the cap
        draw_raw(c, direct_vm, direct_bob, 1)
    advance(direct_vm, 20 * DAY)
    repay(c, direct_vm, direct_bob, 1000)  # token payment: not an installment
    assert c.get_borrower_schedule(k)["installments_paid"] == 0
    with direct_vm.expect_revert("ERR_TRANCHE_CAP"):
        draw_raw(c, direct_vm, direct_bob, 1)


def test_tranche_two_blocked_for_a_full_cycle_after_first_drawdown(c, direct_vm, direct_bob):
    """PoC (audit): draw the first tranche, immediately pay a minimum installment to
    bump installments_paid, and take the rest seconds later. Now refused."""
    k, out = onboard(c, direct_vm, direct_bob)
    limit = int(out["credit_limit"])
    draw_raw(c, direct_vm, direct_bob, limit // 2)
    repay(c, direct_vm, direct_bob, int(c.get_borrower_schedule(k)["minimum_payment"]))
    assert c.get_borrower_schedule(k)["installments_paid"] == 1  # the bypass attempt
    with direct_vm.expect_revert("ERR_TRANCHE_COOLDOWN_ACTIVE"):
        draw_raw(c, direct_vm, direct_bob, MIN_DRAW)
    advance(direct_vm, PAYMENT_CYCLE - 60)  # one minute short of a full cycle
    with direct_vm.expect_revert("ERR_TRANCHE_COOLDOWN_ACTIVE"):
        draw_raw(c, direct_vm, direct_bob, MIN_DRAW)
    advance(direct_vm, 61)
    s = c.get_borrower_schedule(k)
    assert s["tranche_two_opens_at"] == s["first_draw_at"] + PAYMENT_CYCLE
    repay(c, direct_vm, direct_bob, int(s["minimum_payment"]))  # stay current across the cycle
    owed = int(c.get_borrower_schedule(k)["principal"])
    draw_raw(c, direct_vm, direct_bob, limit - owed)  # tranche 2: the rest of the line
    assert c.get_credit_profile(k)["borrowed_amount"] == str(limit)


def test_tranche_time_lock_needs_both_cycle_and_installment(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob)
    draw_raw(c, direct_vm, direct_bob, int(out["credit_limit"]) // 2)
    advance(direct_vm, PAYMENT_CYCLE + 1)
    # a full cycle has elapsed, but nothing was ever paid -> overdue and capped
    with direct_vm.expect_revert("repayment overdue"):
        draw_raw(c, direct_vm, direct_bob, MIN_DRAW)


def test_second_tranche_helper_path_is_the_only_way(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob)
    limit = int(out["credit_limit"])
    draw_raw(c, direct_vm, direct_bob, limit // 2)
    draw_second_tranche(c, direct_vm, direct_bob, MIN_DRAW)
    assert int(c.get_borrower_schedule(k)["principal"]) > limit // 2 - limit // 12


def test_delinquent_borrower_cannot_open_the_second_tranche(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob)
    draw_raw(c, direct_vm, direct_bob, int(out["credit_limit"]) // 2)
    advance(direct_vm, 20 * DAY)
    repay(c, direct_vm, direct_bob, int(c.get_borrower_schedule(k)["minimum_payment"]))
    advance(direct_vm, 31 * DAY)  # misses the next due date
    with direct_vm.expect_revert("repayment overdue"):
        draw_raw(c, direct_vm, direct_bob, MIN_DRAW)


def test_sybil_extraction_yields_half_per_identity(c, direct_vm, direct_bob, direct_charlie):
    """Two identities with self-made telemetry each get at most half their line on day one."""
    total = 0
    for who, name in ((direct_bob, "S1"), (direct_charlie, "S2")):
        k, out = onboard(c, direct_vm, who, limit=ATTO, name=name)
        with direct_vm.expect_revert("ERR_TRANCHE_CAP"):
            draw_raw(c, direct_vm, who, int(out["credit_limit"]))
        draw_raw(c, direct_vm, who, int(out["credit_limit"]) // 2)
        total += int(out["credit_limit"]) // 2
    assert int(c.get_pool_metrics()["borrowed_liquidity"]) == total == ATTO


# ============ FINAL AUDIT: pause after a major liquidation ============
def test_major_liquidation_pauses_new_drawdowns(c, direct_vm, direct_bob, direct_charlie, direct_owner):
    kb, _ = onboard(c, direct_vm, direct_bob, limit=3 * ATTO)
    onboard(c, direct_vm, direct_charlie, limit=ATTO, name="Next")
    draw(c, direct_vm, direct_bob, 3 * ATTO // 2)  # 30% of the pool
    advance(direct_vm, 40 * DAY)
    send(direct_vm, direct_owner)
    c.liquidate_borrower(kb)
    until = c.get_pool_metrics()["drawdown_paused_until"]
    assert until > 0
    with direct_vm.expect_revert("ERR_POOL_PAUSED"):
        draw_raw(c, direct_vm, direct_charlie, MIN_DRAW)  # no instant recycling of the freed liquidity
    advance(direct_vm, 72 * 3600 + 1)
    draw_raw(c, direct_vm, direct_charlie, MIN_DRAW)


def test_minor_liquidation_does_not_pause(c, direct_vm, direct_alice, direct_bob, direct_charlie, direct_owner):
    deposit(c, direct_vm, direct_alice, 5 * ATTO)  # 10 GEN pool: a 0.5 GEN default is 5%
    kb, _ = onboard(c, direct_vm, direct_bob, limit=ATTO, name="Small")
    onboard(c, direct_vm, direct_charlie, limit=ATTO, name="Next")
    draw(c, direct_vm, direct_bob, MIN_DRAW)
    advance(direct_vm, 40 * DAY)
    send(direct_vm, direct_owner)
    c.liquidate_borrower(kb)
    assert c.get_pool_metrics()["drawdown_paused_until"] == 0
    draw_raw(c, direct_vm, direct_charlie, MIN_DRAW)


# ============ FINAL AUDIT 3: dust floor and slot eviction ============
def test_dust_drawdown_is_refused(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob, limit=ATTO)
    for dust in (1, 10**15, MIN_DRAW - 1):
        with direct_vm.expect_revert("ERR_DRAWDOWN_TOO_SMALL"):
            draw_raw(c, direct_vm, direct_bob, dust)
    assert c.get_pool_metrics()["active_borrowers"] == 0  # no slot was squatted
    draw_raw(c, direct_vm, direct_bob, MIN_DRAW)  # exactly the floor is fine
    assert c.get_pool_metrics()["active_borrowers"] == 1


def test_lines_too_small_for_the_floor_cannot_squat_a_slot(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, body=hyperscale(), limit=ATTO, name="Tiny")
    assert int(out["credit_limit"]) < MIN_DRAW  # a C-rated 0.115 GEN line
    with direct_vm.expect_revert():
        draw_raw(c, direct_vm, direct_bob, int(out["credit_limit"]) // 2)
    assert c.get_pool_metrics()["active_borrowers"] == 0


def test_borrower_evicted_the_moment_debt_hits_zero(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw_raw(c, direct_vm, direct_bob, MIN_DRAW)
    assert c.get_pool_metrics()["active_borrowers"] == 1
    repay(c, direct_vm, direct_bob, int(c.get_borrower_schedule(k)["total_owed"]))
    assert c.get_pool_metrics()["active_borrowers"] == 0
    assert c.get_credit_profile(k)["borrowed_amount"] == "0"


def test_partial_repayment_keeps_the_slot(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw_raw(c, direct_vm, direct_bob, MIN_DRAW)
    repay(c, direct_vm, direct_bob, MIN_DRAW // 2)
    assert c.get_pool_metrics()["active_borrowers"] == 1


def test_pause_does_not_block_repayment_or_lp_exit(c, direct_vm, direct_alice, direct_bob, direct_charlie, direct_owner):
    kb, _ = onboard(c, direct_vm, direct_bob, limit=3 * ATTO)
    kc, _ = onboard(c, direct_vm, direct_charlie, limit=ATTO, name="Next")
    draw(c, direct_vm, direct_bob, 3 * ATTO // 2)
    draw(c, direct_vm, direct_charlie, ATTO // 2)
    advance(direct_vm, 40 * DAY)
    send(direct_vm, direct_owner)
    c.liquidate_borrower(kb)
    assert c.get_pool_metrics()["drawdown_paused_until"] > 0
    repay(c, direct_vm, direct_charlie, ATTO // 10)
    send(direct_vm, direct_alice)
    assert int(c.withdraw_lp_capital(ATTO // 10)) == ATTO // 10
