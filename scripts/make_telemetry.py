"""Generate the three borrower telemetry documents with valid proof digests.

Run after editing the figures:  .venv/bin/python scripts/make_telemetry.py
The files under telemetry/ must be served over public https for validators to
fetch them (see README, "Hosting the telemetry feeds").
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import load_accounts  # noqa: E402  (keys come from the git-ignored .env)

OUT = Path(__file__).resolve().parent.parent / "telemetry"


def txlog(total: int, n: int, salt: str):
    each = total // n
    txs = [
        {"tx": "0x" + hashlib.sha256(f"{salt}-{i}".encode()).hexdigest(), "amount_usd": each}
        for i in range(n)
    ]
    return txs, each * n


def digest(txs) -> str:
    return hashlib.sha256(json.dumps(txs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def doc(name, who, rev, opex, burn, treasury, inflow, n, narrative, ds=0):
    txs, total = txlog(inflow, n, name)
    return {
        "company": name,
        # Identity binding: the contract rejects this file for any other address
        # (ERR_BORROWER_MISMATCH). Testnet PoC: unsigned self-attestation; see README.
        "borrower_address": ACCOUNTS[who].address,
        "period": "2026-09",
        "monthly_revenue_usd": rev,
        "monthly_opex_usd": opex,
        "monthly_burn_usd": burn,
        "treasury_usd": treasury,
        "existing_annual_debt_service_usd": ds,
        "claimed_arr_usd": rev * 12,
        "transactions": txs,
        "proof_sha256": digest(txs),
        "verified_onchain_inflows_usd": total,
        "narrative": narrative,
    }


ACCOUNTS = load_accounts()

DOCS = {
    # ARR $2.5M, net burn $25k vs $700k treasury -> 28 months runway, DSCR ~3.8x
    "aether": doc("Aether Infrastructure", "AETHER", 208_334, 100_000, 233_334, 700_000, 150_000, 6,
                  "Enterprise SaaS infrastructure. 214 contracted customers, no customer above 6% of revenue, "
                  "94% gross retention, annual prepaid contracts."),
    # Burning cash: opex 3x revenue, ~2 months runway, negative operating income
    "hyperscale": doc("HyperScale Labs", "HYPERSCALE", 60_000, 180_000, 260_000, 400_000, 12_000, 3,
                      "Growth-stage compute marketplace. Revenue concentrated in two customers; "
                      "hiring ahead of demand."),
    # Left PENDING for live steward review: ARR $960k, runway ~22 months
    "zeroproof": doc("ZeroProof Systems", "ZEROPROOF", 80_000, 30_000, 95_000, 330_000, 60_000, 4,
                     "Real-time proof-of-reserves telemetry. Protocol fees paid in stablecoins, "
                     "diversified across 31 integrators."),
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for key, body in DOCS.items():
        (OUT / f"{key}.json").write_text(json.dumps(body, indent=2) + "\n")
        print(f"wrote telemetry/{key}.json  proof={body['proof_sha256'][:16]}...")
