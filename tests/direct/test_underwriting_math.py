"""Rating corridor: Runway / DSCR / ARR arithmetic and ceiling clamping.

underwrite_preview(revenue, opex, burn, treasury, inflows, existing_ds, requested_usd)
"""
import pytest
from conftest import *


@pytest.fixture
def c(direct_deploy):
    return direct_deploy(CONTRACT)


def uw(c, rev=208_334, opex=100_000, burn=233_334, treasury=700_000, inflows=150_000, ds=0, req=750_000):
    return c.underwrite_preview(rev, opex, burn, treasury, inflows, ds, req)


def test_arr_is_twelve_times_revenue(c):
    assert uw(c, rev=100_000)["arr"] == 1_200_000


def test_runway_is_treasury_over_net_burn(c):
    # net burn = 233_334 - 208_334 = 25_000 ; 700_000 / 25_000 = 28.0
    assert uw(c)["runway_x100"] == 2800


def test_runway_unbounded_when_cash_flow_positive(c):
    assert uw(c, burn=150_000)["runway_x100"] == 99900


def test_runway_fractional_months(c):
    assert uw(c, treasury=62_500)["runway_x100"] == 250


def test_dscr_formula(c):
    # NOI = 12 * 108_334 = 1_300_008 ; DS = 750_000 * 0.4533 = 339_975
    assert uw(c)["dscr_x100"] == 1_300_008 * 100 // 339_975


def test_dscr_includes_existing_debt_service(c):
    assert uw(c, ds=500_000)["dscr_x100"] < uw(c)["dscr_x100"]


def test_dscr_zero_when_noi_negative(c):
    assert uw(c, opex=300_000)["dscr_x100"] == 0


def test_dscr_zero_when_noi_exactly_zero(c):
    assert uw(c, opex=208_334)["dscr_x100"] == 0


def test_dscr_unbounded_when_no_debt_service(c):
    assert uw(c, req=0)["dscr_x100"] == 99900


def test_aaa_when_all_thresholds_clear(c):
    assert uw(c)["ceiling"] == "AAA"


def test_aaa_requires_24_month_runway(c):
    # exactly 24.00 months: net burn 25_000, treasury 600_000
    assert uw(c, treasury=600_000)["ceiling"] == "AAA"
    assert uw(c, treasury=599_975)["ceiling"] != "AAA"


def test_aaa_requires_dscr_2_5(c):
    assert uw(c, req=750_000)["ceiling"] == "AAA"
    low = uw(c, req=2_000_000)  # DS 906k -> DSCR 1.43
    assert low["dscr_x100"] < 250 and low["ceiling"] != "AAA"


def test_aaa_requires_one_million_arr(c):
    # ARR 960_000 (<1M) with strong ratios cannot be AAA
    r = uw(c, rev=80_000, opex=30_000, burn=95_000, treasury=330_000, inflows=60_000, req=250_000)
    assert r["arr"] == 960_000 and r["ceiling"] == "AA"


def test_investment_grade_floor_runway_12(c):
    ok = uw(c, treasury=300_000)   # 12.0 months
    bad = uw(c, treasury=299_975)
    assert ok["ceiling"] in ("AAA", "AA", "A", "BBB")
    assert bad["ceiling"] in ("BB", "B", "C")


def test_investment_grade_floor_dscr_125(c):
    # tune requested notional so DSCR lands just under 1.25
    r = uw(c, req=2_500_000)
    assert r["dscr_x100"] < 125 and r["ceiling"] in ("BB", "B", "C")


@pytest.mark.parametrize("treasury", [0, 10_000, 50_000, 100_000, 250_000, 299_000])
def test_failing_bbb_is_strictly_speculative(c, treasury):
    assert uw(c, treasury=treasury)["ceiling"] in ("BB", "B", "C")


def test_bb_needs_runway_6_and_dscr_1(c):
    r = uw(c, treasury=150_000)  # 6.0 months
    assert r["ceiling"] == "BB"


def test_b_tier(c):
    r = uw(c, treasury=75_000)  # 3.0 months
    assert r["ceiling"] == "B"


def test_c_tier_when_burning_and_negative_noi(c):
    r = uw(c, rev=60_000, opex=180_000, burn=260_000, treasury=400_000, inflows=12_000, req=250_000)
    assert r["ceiling"] == "C" and r["dscr_x100"] == 0


def test_low_corroboration_caps_at_bb(c):
    r = uw(c, inflows=1_000)  # <10% of revenue
    assert r["corroboration_bps"] < 1000 and r["ceiling"] == "BB"


def test_corroboration_capped_at_100_percent(c):
    assert uw(c, inflows=10**9)["corroboration_bps"] == 10_000


@pytest.mark.parametrize("rating,adv", [("AAA", 4000), ("AA", 3500), ("A", 3000), ("BBB", 2500),
                                        ("BB", 1500), ("B", 800), ("C", 400)])
def test_rating_table_advance_rates(c, rating, adv):
    row = [r for r in c.get_rating_table() if r["rating"] == rating][0]
    assert row["advance_bps"] == adv


@pytest.mark.parametrize("rating,rate", [("AAA", 400), ("AA", 600), ("A", 850), ("BBB", 1200),
                                         ("BB", 1800), ("B", 2500), ("C", 3500)])
def test_rating_table_rates_match_spec(c, rating, rate):
    row = [r for r in c.get_rating_table() if r["rating"] == rating][0]
    assert row["rate_bps"] == rate


def test_rating_table_ordered_best_first(c):
    assert [r["rating"] for r in c.get_rating_table()] == ["AAA", "AA", "A", "BBB", "BB", "B", "C"]
    rates = [r["rate_bps"] for r in c.get_rating_table()]
    assert rates == sorted(rates)


def test_limit_usd_bounded_by_request(c):
    r = uw(c, req=100_000)
    assert r["limit_usd"] == 100_000


def test_limit_usd_bounded_by_advance_rate(c):
    r = uw(c, req=50_000_000)
    assert r["limit_usd"] == r["arr"] * 4000 // 10000 or r["limit_usd"] <= r["arr"]


def test_preview_rejects_negative_inputs(c, direct_vm):
    with direct_vm.expect_revert("non-negative"):
        c.underwrite_preview(-1, 0, 0, 0, 0, 0, 1)


def test_preview_rejects_zero_revenue(c, direct_vm):
    with direct_vm.expect_revert("revenue positive"):
        c.underwrite_preview(0, 0, 0, 0, 0, 0, 1)
