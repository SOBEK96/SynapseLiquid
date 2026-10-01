"""Deploy contracts/synapse_liquid.py to GenLayer Studio Next and seed the pool.

    .venv/bin/python scripts/deploy.py [--liquidity 5.0]

1. derive / generate the local keys in .env (git-ignored, mode 600)
2. fund the deployer through the sim_fundAccount RPC (10 GEN)
3. deploy the contract (chain 61997)
4. seed the lending pool with LP capital
5. record address, source SHA-256 and tx hashes in deployments/studio-next.json
"""

import argparse
import json
from datetime import datetime, timezone

from lib import (ATTO, CHAIN_ID, CONTRACT_PATH, EXPLORER, RPC_URL, Chain, explorer_address, load_accounts,
                 load_deployment, save_deployment, source_sha256, tx_url)

RUNNER = "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liquidity", type=float, default=5.0, help="GEN to seed into the pool")
    ap.add_argument("--redeploy", action="store_true", help="deploy a fresh contract even if one is recorded")
    args = ap.parse_args()

    accounts = load_accounts()
    deployer = Chain(accounts["DEPLOYER"])
    print(f"deployer {deployer.address}  (chain {CHAIN_ID})")

    if deployer.fund(10 * ATTO):
        print("  funded via sim_fundAccount -> 10 GEN")
    print(f"  balance {deployer.balance() / ATTO:.4f} GEN")

    rec = load_deployment()
    code = CONTRACT_PATH.read_bytes()
    sha = source_sha256()

    if rec.get("contract_address") and not args.redeploy and rec.get("source_sha256_at_record") == sha:
        print(f"contract already deployed at {rec['contract_address']} (source unchanged)")
    else:
        addr, receipt = deployer.deploy(code, "deploy synapse_liquid")
        rec = {
            "network": "studio-next",
            "chain_id": CHAIN_ID,
            "rpc_url": RPC_URL,
            "contract_address": addr,
            "explorer_url": explorer_address(addr),
            "source": "contracts/synapse_liquid.py",
            "runner": RUNNER,
            "source_sha256_at_record": sha,
            "deployer": deployer.address,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "transactions": [{"label": "deploy", "hash": receipt["_tx_hash"], "url": tx_url(receipt["_tx_hash"])}],
        }
        save_deployment(rec)
        print(f"deployed at {addr}")

    deployer.contract = rec["contract_address"]
    metrics = deployer.read("get_pool_metrics")
    seeded = int(metrics["total_deposited"])
    want = int(args.liquidity * ATTO)
    if seeded >= want:
        print(f"pool already holds {seeded / ATTO} GEN")
    else:
        receipt = deployer.write("deposit_liquidity", value=want - seeded, label="seed liquidity")
        rec["transactions"].append(
            {"label": f"seed_liquidity {(want - seeded) / ATTO} GEN", "hash": receipt["_tx_hash"],
             "url": tx_url(receipt["_tx_hash"])}
        )
        save_deployment(rec)
        print(f"seeded {(want - seeded) / ATTO} GEN")

    print(json.dumps(deployer.read("get_pool_metrics"), indent=2))
    print(f"explorer: {rec['explorer_url']}")


if __name__ == "__main__":
    main()
