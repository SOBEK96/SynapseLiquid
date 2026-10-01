"""Shared helpers for the SynapseLiquid deploy / live-proof scripts.

Keys live in a git-ignored `.env` (mode 600). Every network call goes through
`Chain`, which mirrors the fee and receipt handling Studio Next requires.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from genlayer_py import create_account, create_client
from genlayer_py.chains import studio_devnet  # type: ignore[reportAttributeAccessIssue]

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
CONTRACT_PATH = ROOT / "contracts" / "synapse_liquid.py"
DEPLOYMENT_PATH = ROOT / "deployments" / "studio-next.json"

CHAIN_ID = 61997
RPC_URL = "https://studio-next.genlayer.com/api"
EXPLORER = "https://explorer-studio-next.genlayer.com"
ATTO = 10**18
BOND = ATTO // 10

KEY_NAMES = ("DEPLOYER", "AETHER", "HYPERSCALE", "ZEROPROOF")


# --------------------------------------------------------------------- .env keys
def _read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def load_accounts() -> dict[str, Any]:
    """Return {name: LocalAccount}, generating and persisting any missing key.
    The file is created with mode 600 before any secret is written to it."""
    env = _read_env()
    created = False
    for name in KEY_NAMES:
        var = f"{name}_PRIVATE_KEY"
        if var not in env:
            env[var] = "0x" + create_account().key.hex().removeprefix("0x")
            created = True
    if created or not ENV_PATH.exists():
        fd = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write("# SynapseLiquid local keys (git-ignored). Studio Next test accounts only.\n")
            for k, v in env.items():
                fh.write(f"{k}={v}\n")
        os.chmod(ENV_PATH, 0o600)
    return {name: create_account(env[f"{name}_PRIVATE_KEY"]) for name in KEY_NAMES}


def telemetry_base_url() -> str:
    base = os.environ.get("TELEMETRY_BASE_URL") or _read_env().get("TELEMETRY_BASE_URL", "")
    return base.rstrip("/")


# ------------------------------------------------------------------- deployments
def load_deployment() -> dict:
    if DEPLOYMENT_PATH.exists():
        return json.loads(DEPLOYMENT_PATH.read_text())
    return {}


def save_deployment(data: dict) -> None:
    DEPLOYMENT_PATH.parent.mkdir(exist_ok=True)
    DEPLOYMENT_PATH.write_text(json.dumps(data, indent=2) + "\n")


def source_sha256() -> str:
    return hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()


def tx_url(tx_hash: str) -> str:
    return f"{EXPLORER}/transactions/{tx_hash}"


# ---------------------------------------------------------------------- the chain
class ChainError(Exception):
    pass


_OK_EXEC = "FINISHED_WITH_RETURN"
_OK_CONSENSUS = "MAJORITY_AGREE"


def _retry(fn, attempts: int = 4, wait_s: float = 6.0):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except ChainError:
            raise
        except Exception as exc:  # noqa: BLE001 - transient transport errors
            last = exc
            if i + 1 < attempts:
                time.sleep(wait_s * (i + 1))
    raise ChainError(f"transient RPC failure after {attempts} attempts: {last}")


def _hex(tx_hash) -> str:
    h = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    return h if h.startswith("0x") else "0x" + h


class Chain:
    def __init__(self, account, contract: str | None = None):
        self.account = account
        self.contract = contract
        self.client = create_client(chain=studio_devnet, account=account)

    @property
    def address(self) -> str:
        return self.account.address

    def balance(self) -> int:
        resp = _retry(lambda: self.client.provider.make_request("eth_getBalance", [self.address, "latest"]))
        return int(resp.get("result", "0x0"), 16)

    def fund(self, target_wei: int) -> bool:
        """sim_fundAccount top-up until the wallet holds `target_wei`."""
        have = self.balance()
        if have >= target_wei:
            return False
        _retry(lambda: self.client.fund_account(self.address, target_wei - have))
        return True

    def read(self, method: str, args: list | None = None):
        return _retry(lambda: self.client.read_contract(self.contract, method, args=args or []))

    def _fees(self, method: str | None, args: list, value: int) -> dict:
        from genlayer_py.contracts.actions import (  # noqa: PLC0415
            _estimate_transaction_fees_with_policy,
            get_current_fee_policy,
        )

        est = _retry(lambda: _estimate_transaction_fees_with_policy(self.client, None, get_current_fee_policy(self.client)))
        fees = {"distribution": est["distribution"], "feeValue": est.get("feeValue") or est.get("fee_value") or 0}
        if est.get("messageAllocations") is not None:
            fees["messageAllocations"] = est["messageAllocations"]
        return fees

    def _wait(self, tx_hash, label: str) -> dict:
        print(f"    tx {label}: {_hex(tx_hash)[:20]}... waiting for consensus", flush=True)
        receipt = _retry(
            lambda: self.client.wait_for_transaction_receipt(
                tx_hash, wait_until="decided", interval=4, retries=150  # type: ignore[reportCallIssue]
            ),
            attempts=3,
        )
        exec_name = receipt.get("txExecutionResultName") or receipt.get("tx_execution_result_name")
        consensus = receipt.get("result_name")
        if exec_name is not None and exec_name != _OK_EXEC:
            raise ChainError(f"{label}: execution failed ({exec_name})")
        if consensus is not None and consensus != _OK_CONSENSUS:
            raise ChainError(f"{label}: consensus {consensus}")
        receipt["_tx_hash"] = _hex(tx_hash)
        return receipt

    def write(self, method: str, args: list | None = None, value: int = 0, label: str = "") -> dict:
        args = args or []
        fees = self._fees(method, args, value)
        tx_hash = _retry(
            lambda: self.client.write_contract(self.contract, method, args=args, value=value, fees=fees),
            attempts=1,
        )
        return self._wait(tx_hash, label or method)

    def deploy(self, code: bytes, label: str = "deploy") -> tuple[str, dict]:
        fees = self._fees(None, [], 0)
        tx_hash = _retry(lambda: self.client.deploy_contract(code=code, args=[], fees=fees), attempts=1)
        receipt = self._wait(tx_hash, label)
        addr = contract_address_from(receipt)
        if not addr:
            tx = _retry(lambda: self.client.get_transaction(tx_hash))
            addr = contract_address_from(tx) or tx.get("to_address") or tx.get("recipient")
        if not addr:
            raise ChainError(f"no contract address in receipt: {json.dumps(receipt, default=str)[:400]}")
        return addr, receipt

    def tx_result(self, tx_hash: str) -> Any:
        """Best-effort decode of what the contract returned for `tx_hash`."""
        tx = _retry(lambda: self.client.get_transaction(tx_hash))
        consensus = tx.get("consensus_data") or {}
        for leader in consensus.get("leader_receipt") or []:
            res = leader.get("result")
            payload = None
            if isinstance(res, dict):
                payload = res.get("payload") or res.get("raw")
            elif isinstance(res, str):
                payload = res
            if isinstance(payload, str) and payload:
                return payload
        return None


def contract_address_from(obj: dict) -> str | None:
    for path in (("txDataDecoded", "contractAddress"), ("data", "contract_address"),
                 ("txDataDecoded", "contract_address")):
        cur: Any = obj
        for p in path:
            cur = cur.get(p) if isinstance(cur, dict) else None
        if isinstance(cur, str) and cur:
            return cur
    for k in ("contractAddress", "contract_address"):
        if isinstance(obj.get(k), str):
            return obj[k]
    return None


def explorer_address(addr: str) -> str:
    return f"{EXPLORER}/address/{addr}"


def b64_text(s: str) -> str:
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:
        return s
