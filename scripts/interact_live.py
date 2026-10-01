"""Seed and drive the three live corporate credit positions on Studio Next.

    TELEMETRY_BASE_URL=https://.../telemetry .venv/bin/python scripts/interact_live.py seed
    .venv/bin/python scripts/interact_live.py assess-zeroproof    # live steward review
    .venv/bin/python scripts/interact_live.py status

  seed             Entity #1 Aether (AAA, drawn down), #2 HyperScale (C),
                   #3 ZeroProof (left PENDING). Idempotent: skips finished steps.
  assess-zeroproof run consensus assessment for the PENDING entity #3
  status           print pool metrics and every credit profile

Telemetry documents (telemetry/*.json) must be reachable over public https at
$TELEMETRY_BASE_URL/<name>.json; each is fetched and its proof digest verified
locally BEFORE any bond is posted, so a mis-hosted feed cannot cost a bond.
"""

import hashlib
import json
import sys
import urllib.request

from lib import (ATTO, BOND, Chain, ChainError, load_accounts, load_deployment, save_deployment,
                 telemetry_base_url, tx_url)

ENTITIES = {
    # name, company, requested limit (GEN), draw (GEN)
    "AETHER": ("aether", "Aether Infrastructure", 3 * ATTO, 3 * ATTO // 2),
    "HYPERSCALE": ("hyperscale", "HyperScale Labs", ATTO, 0),
    "ZEROPROOF": ("zeroproof", "ZeroProof Systems", 2 * ATTO, 0),
}


def digest(txs) -> str:
    return hashlib.sha256(json.dumps(txs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def preflight_feed(url: str) -> None:
    """Fetch the feed exactly as a validator would and check its proof."""
    with urllib.request.urlopen(url, timeout=20) as r:  # noqa: S310 - https URL we host
        if r.status != 200:
            raise SystemExit(f"telemetry feed {url} returned HTTP {r.status}")
        body = json.loads(r.read())
    if body.get("proof_sha256") != digest(body.get("transactions", [])):
        raise SystemExit(f"telemetry feed {url} fails its own proof digest")
    print(f"    feed ok: {url}")


def record(rec: dict, label: str, receipt: dict) -> None:
    rec.setdefault("transactions", []).append(
        {"label": label, "hash": receipt["_tx_hash"], "url": tx_url(receipt["_tx_hash"])}
    )
    save_deployment(rec)


def profile(chain: Chain):
    try:
        return chain.read("get_credit_profile", [chain.address])
    except Exception:  # noqa: BLE001 - unknown borrower reverts
        return None


def seed_entity(rec: dict, name: str, chain: Chain) -> None:
    slug, company, limit, draw = ENTITIES[name]
    base = telemetry_base_url()
    if not base:
        raise SystemExit("set TELEMETRY_BASE_URL to the public https folder serving telemetry/*.json")
    url = f"{base}/{slug}.json"
    print(f"[{company}] {chain.address}")
    p = profile(chain)
    if p is None or p["status"] in ("INCONCLUSIVE", "CLOSED"):
        preflight_feed(url)
        chain.fund(2 * ATTO)
        record(rec, f"apply_for_credit {company}", chain.write("apply_for_credit", [company, url, limit], BOND, f"apply {slug}"))
        p = profile(chain)
    if name == "ZEROPROOF":
        print(f"    left {p['status']} for live steward review")
        return
    if p["status"] == "PENDING":
        receipt = chain.write("assess_credit_consensus", [chain.address], 0, f"assess {slug}")
        record(rec, f"assess_credit_consensus {company}", receipt)
        p = profile(chain)
    print(f"    status={p['status']} rating={p['rating']} rate={p['interest_rate_bps']}bps "
          f"dscr={p['dscr_ratio'] / 100:.2f} runway={p['runway_months']}mo limit={int(p['credit_limit']) / ATTO} GEN")
    if draw and p["status"] == "ACTIVE" and int(p["borrowed_amount"]) == 0:
        record(rec, f"drawdown_credit {draw / ATTO} GEN {company}", chain.write("drawdown_credit", [draw], 0, f"draw {slug}"))
        print(f"    drew {draw / ATTO} GEN")


def status(chain: Chain) -> None:
    print(json.dumps(chain.read("get_pool_metrics"), indent=2))
    for i in range(int(chain.read("get_borrower_count"))):
        k = chain.read("get_borrower_at", [i])
        p = chain.read("get_credit_profile", [k])
        print(f"#{i + 1} {p['company_name']:<24} {p['status']:<10} {p['rating']:<8} "
              f"{p['interest_rate_bps']:>5}bps  dscr {p['dscr_ratio'] / 100:.2f}  borrowed {int(p['borrowed_amount']) / ATTO} GEN")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    rec = load_deployment()
    if not rec.get("contract_address"):
        raise SystemExit("no deployment recorded: run scripts/deploy.py first")
    accounts = load_accounts()
    chains = {n: Chain(a, rec["contract_address"]) for n, a in accounts.items()}
    try:
        if cmd == "seed":
            for name in ("AETHER", "HYPERSCALE", "ZEROPROOF"):
                seed_entity(rec, name, chains[name])
            status(chains["DEPLOYER"])
        elif cmd == "assess-zeroproof":
            c = chains["DEPLOYER"]  # permissionless: any steward may trigger consensus
            c.fund(ATTO)
            z = chains["ZEROPROOF"].address
            record(rec, "assess_credit_consensus ZeroProof Systems", c.write("assess_credit_consensus", [z], 0, "assess zeroproof"))
            status(c)
        else:
            status(chains["DEPLOYER"])
    except ChainError as e:
        raise SystemExit(f"chain error: {e}")


if __name__ == "__main__":
    main()
