"""Regenerate the live-proofs table in README.md from deployments/studio-next.json."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
dep = json.loads((ROOT / "deployments" / "studio-next.json").read_text())
rows = ["| # | Action | Transaction |", "|---|--------|-------------|"]
for i, t in enumerate(dep.get("transactions", []), 1):
    rows.append(f"| {i} | {t['label']} | [`{t['hash'][:10]}…{t['hash'][-8:]}`]({t['url']}) |")
block = "\n".join(
    [
        "<!-- PROOFS:START -->",
        f"- **Network:** GenLayer Studio Next · chain `{dep['chain_id']}` (`0xF22D`) · RPC `{dep['rpc_url']}`",
        f"- **Contract:** [`{dep['contract_address']}`]({dep['explorer_url']})",
        f"- **Source SHA-256 (`contracts/synapse_liquid.py`):** `{dep['source_sha256_at_record']}`",
        f"- **Runner:** `{dep['runner']}`",
        f"- **Deployed:** {dep['deployed_at']}",
        *[f"- **Superseded (pre-audit) contract:** [`{d['contract_address']}`]({d['explorer_url']}) — do not use"
          for d in dep.get("previous_deployments", [])],
        "",
        *rows,
        "<!-- PROOFS:END -->",
    ]
)
readme = ROOT / "README.md"
text = readme.read_text()
text = re.sub(r"<!-- PROOFS:START -->.*?<!-- PROOFS:END -->", lambda _: block, text, flags=re.S)
readme.write_text(text)
print(f"README proofs updated ({len(dep.get('transactions', []))} transactions)")
