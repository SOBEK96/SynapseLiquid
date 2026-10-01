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
def test_global_utilization_cap_enforced(c, direct_vm, direct_bob, direct_charlie):
    """PoC: two borrowers, each inside its own limit, together breach 60%."""
    onboard(c, direct_vm, direct_bob, limit=3 * ATTO)
    onboard(c, direct_vm, direct_charlie, limit=5 * ATTO // 4, name="Second Co")
    draw(c, direct_vm, direct_bob, 5 * ATTO // 2)           # 50% utilised
    with direct_vm.expect_revert("ERR_POOL_CAP_REACHED"):
        draw(c, direct_vm, direct_charlie, 6 * ATTO // 10)  # 3.1 / 5 > 60%
    draw(c, direct_vm, direct_charlie, 5 * ATTO // 10)      # exactly 3.0 / 5 == 60%
    assert c.get_pool_metrics()["utilization_bps"] == MAX_UTIL_BPS
    with direct_vm.expect_revert("ERR_POOL_CAP_REACHED"):
        draw(c, direct_vm, direct_charlie, 1)


def test_sybil_swarm_cannot_pass_the_cap(c, direct_vm, direct_bob, direct_charlie, direct_owner, direct_alice):
    for who, name in ((direct_bob, "S1"), (direct_charlie, "S2"), (direct_owner, "S3")):
        onboard(c, direct_vm, who, limit=ATTO, name=name)
    draw(c, direct_vm, direct_bob, ATTO)
    draw(c, direct_vm, direct_charlie, ATTO)
    draw(c, direct_vm, direct_owner, ATTO)  # 3 / 5 == 60%
    onboard(c, direct_vm, direct_alice, limit=ATTO, name="S4")
    with direct_vm.expect_revert("ERR_POOL_CAP_REACHED"):
        draw(c, direct_vm, direct_alice, 1)
    assert int(c.get_pool_metrics()["borrowed_liquidity"]) <= 3 * ATTO


def test_cap_binds_even_when_own_limit_is_larger(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, limit=4 * ATTO)
    assert int(out["credit_limit"]) <= 3 * ATTO  # concentration cap at assessment
    with direct_vm.expect_revert("exceeds credit limit"):
        draw(c, direct_vm, direct_bob, 3 * ATTO + 1)


def test_repayment_frees_cap_headroom(c, direct_vm, direct_bob, direct_charlie):
    onboard(c, direct_vm, direct_bob, limit=3 * ATTO)
    onboard(c, direct_vm, direct_charlie, limit=ATTO, name="Second Co")
    draw(c, direct_vm, direct_bob, 3 * ATTO)
    with direct_vm.expect_revert("ERR_POOL_CAP_REACHED"):
        draw(c, direct_vm, direct_charlie, 1)
    repay(c, direct_vm, direct_bob, ATTO)
    draw(c, direct_vm, direct_charlie, ATTO)


# ------------------------------------------------ FINDING 3: bad-debt haircut
def _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    deposit(c, direct_vm, direct_bob, 2 * ATTO)  # alice 5 + bob 2 = 7 GEN; cap 4.2
    onboard(c, direct_vm, direct_charlie, limit=3 * ATTO)
    draw(c, direct_vm, direct_charlie, 3 * ATTO)


def test_delinquent_loan_bad_debt_haircut(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    """PoC: once a loan is overdue the early LP could withdraw at par and leave
    the loss to the last LP. Now the loss is marked to market for everyone."""
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    before = int(c.get_lp_position(key(c, direct_vm, direct_alice))["value"])
    assert before == 5 * ATTO
    advance(direct_vm, 31 * DAY)  # past the due date, before liquidation is allowed
    m = c.get_pool_metrics()
    assert m["delinquent_principal"] == str(3 * ATTO) and c.get_total_assets() == str(4 * ATTO)
    a = c.get_lp_position(key(c, direct_vm, direct_alice))
    b = c.get_lp_position(key(c, direct_vm, direct_bob))
    assert int(a["value"]) == 5 * ATTO * 4 // 7 and int(b["value"]) == 2 * ATTO * 4 // 7
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
    assert ratio_a == pytest.approx(4 / 7, rel=1e-6)
    assert ratio_b == pytest.approx(ratio_a, rel=1e-6)  # identical recovery: no first-mover advantage


def test_withdrawal_is_capped_by_haircut_value(c, direct_vm, direct_alice, direct_bob, direct_charlie):
    _setup_delinquent(c, direct_vm, direct_alice, direct_bob, direct_charlie)
    advance(direct_vm, 31 * DAY)
    send(direct_vm, direct_alice)
    with direct_vm.expect_revert("exceeds position value"):
        c.withdraw_lp_capital(5 * ATTO * 4 // 7 + 10**12)


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
    draw(c, direct_vm, direct_bob, 3 * ATTO)
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
    draw(c, direct_vm, direct_bob, 2 * ATTO)
    expiry = c.get_borrower_schedule(k)["loan_expiry"]
    start = c.get_credit_profile(k)["last_assessment_timestamp"]
    assert expiry == start + 365 * DAY
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
    draw(c, direct_vm, direct_bob, 2 * ATTO)
    advance(direct_vm, 340 * DAY)
    s = c.get_borrower_schedule(k)
    assert s["months_left"] == 1 and s["minimum_payment"] == s["total_owed"]
    repay(c, direct_vm, direct_bob, int(s["minimum_payment"]))
    assert c.get_borrower_schedule(k)["principal"] == "0"


def test_matured_loan_is_delinquent_and_liquidatable(c, direct_vm, direct_bob, direct_charlie):
    """Pay the schedule for 11 months, then stall: the due date cannot roll on,
    and the loan is delinquent at maturity however much was repaid before."""
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, 2 * ATTO)
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
    draw(c, direct_vm, direct_bob, ATTO)
    assert c.get_borrower_schedule(k)["loan_expiry"] == expiry


def test_minimum_instalment_scales_with_time_left(c, direct_vm, direct_bob):
    k, _ = onboard(c, direct_vm, direct_bob)
    draw(c, direct_vm, direct_bob, 2 * ATTO)
    early = c.get_borrower_schedule(k)
    advance(direct_vm, 300 * DAY)
    late = c.get_borrower_schedule(k)
    assert late["months_left"] < early["months_left"]
    assert int(late["minimum_payment"]) - int(late["accrued_interest"]) > 2 * ATTO // 12


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
