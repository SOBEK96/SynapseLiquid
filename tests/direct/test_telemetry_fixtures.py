"""The shipped telemetry/*.json documents resolve to the ratings the README claims."""
import json
from pathlib import Path

import pytest
from conftest import *

TEL = Path(__file__).resolve().parents[2] / "telemetry"


@pytest.fixture
def c(direct_vm, direct_deploy, direct_alice):
    c = direct_deploy(CONTRACT)
    deposit(c, direct_vm, direct_alice, 5 * ATTO)
    return c


def load(name, bound=False):
    """The shipped documents are bound to the live testnet accounts; the harness
    accounts differ, so strip the binding and let onboard() bind to the borrower."""
    doc = json.loads((TEL / f"{name}.json").read_text())
    if not bound:
        doc.pop("borrower_address")
    return doc


@pytest.mark.parametrize("name", ["aether", "hyperscale", "zeroproof"])
def test_fixture_proof_digest_is_valid(name):
    doc = load(name)
    assert doc["proof_sha256"] == proof(doc["transactions"])
    assert doc["verified_onchain_inflows_usd"] == sum(t["amount_usd"] for t in doc["transactions"])


@pytest.mark.parametrize("name", ["aether", "hyperscale", "zeroproof"])
def test_fixture_is_bound_to_an_address(name):
    import re
    assert re.fullmatch(r"0x[0-9a-fA-F]{40}", load(name, bound=True)["borrower_address"])


def test_aether_fixture_is_aaa_28_months(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, body=load("aether"), limit=3 * ATTO)
    p = c.get_credit_profile(k)
    assert out["rating"] == "AAA" and out["interest_rate_bps"] == 400
    assert p["runway_months"] == 28 and p["arr_usd"] == 2_500_008


def test_hyperscale_fixture_is_c(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, body=load("hyperscale"), limit=ATTO, name="HyperScale Labs")
    assert out["rating"] == "C" and out["interest_rate_bps"] == 3500 and out["dscr_x100"] == 0


def test_zeroproof_fixture_ceiling_is_aa(c, direct_vm, direct_bob):
    k, out = onboard(c, direct_vm, direct_bob, body=load("zeroproof"), limit=2 * ATTO, name="ZeroProof Systems")
    assert out["ceiling"] == "AA"
