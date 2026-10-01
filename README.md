# SynapseLiquid

**Autonomous under-collateralised debt market and on-chain credit-rating protocol**, built on
[GenLayer](https://genlayer.com) Studio Next (chain `61997`).

Web3 startups with verifiable cash flows (SaaS subscriptions, protocol fees, treasury inflows) apply for
credit lines against a **proportional underwriting bond** (`max(0.1 GEN, 15% of the requested limit)`). GenVM validators fetch the applicant's JSON
telemetry, verify its cryptographic cash-flow proof, compute **Runway / DSCR / ARR** in integer arithmetic, and
reach multi-LLM consensus under the **Equivalence Principle** on a rating from `AAA` to `C`. The contract binds
the interest rate, credit limit and amortisation schedule directly to that rating.

> Studio Next is a test network. GEN has no market price here; fiat telemetry is converted at a governor-set
> notional (`usd_per_gen`, default $250,000). Nothing in this repository is investment advice.

---

## 1. Live on-chain proofs

<!-- PROOFS:START -->
- **Network:** GenLayer Studio Next · chain `61997` (`0xF22D`) · RPC `https://studio-next.genlayer.com/api`
- **Contract:** [`0xb4c01554C5C30ae3Cc706118460c7887E918650a`](https://explorer-studio-next.genlayer.com/address/0xb4c01554C5C30ae3Cc706118460c7887E918650a)
- **Source SHA-256 (`contracts/synapse_liquid.py`):** `77afa5b24c2e78e4c8b453cd61f3a2816f650e6ee39e9b1f2b239b35107ec8ce`
- **Runner:** `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`
- **Deployed:** 2026-10-01T14:03:21.366513+00:00
- **Superseded (pre-audit) contract:** [`0x83709BEABCeC81C53fB776b37089Cdee976b3069`](https://explorer-studio-next.genlayer.com/address/0x83709BEABCeC81C53fB776b37089Cdee976b3069) — do not use

| # | Action | Transaction |
|---|--------|-------------|
| 1 | deploy | [`0x6adbc15d…9ed8cacf`](https://explorer-studio-next.genlayer.com/transactions/0x6adbc15de70c5c42f1f8a7282cb703bd22c4be9d560302deda3683889ed8cacf) |
| 2 | seed_liquidity 5.0 GEN | [`0xa4c311bc…2529bfb1`](https://explorer-studio-next.genlayer.com/transactions/0xa4c311bc2689d36200d6f55807c16cdff65350ce1a92d978d3d4a71c2529bfb1) |
<!-- PROOFS:END -->

Every row is a Studio Next transaction decided by validator consensus. The contract's own accounting is checked
against the real chain balance by the `solvent` flag in `get_pool_metrics()`.

---

## 2. Quantitative finance theory

All figures are whole USD; every ratio is computed in integers (fixed-point ×100), so each validator derives
bit-identical values. The formulas below are implemented once in `contracts/synapse_liquid.py` (`_underwrite`)
and mirrored for display in `frontend/src/lib/finance.ts`.

```
ARR            = 12 × monthly_revenue
Net burn       = max(0, monthly_burn − monthly_revenue)        monthly_burn = all cash outflows (opex + capex + R&D)
Runway         = treasury ÷ net burn            (months; unbounded when cash-flow positive)
NOI            = monthly_revenue − monthly_opex          (operating, before capex)
Annual DS      = existing_annual_debt_service + requested_limit_usd × (12% + 33.33%)
                                          └ reference coupon      └ 36-month straight-line amortisation
DSCR           = 12 × NOI ÷ Annual DS           (0 when NOI ≤ 0)
Corroboration  = on-chain verified inflows ÷ monthly_revenue   (capped at 100%)
```

**DSCR** (debt-service coverage ratio) answers “how many times does operating income cover the year's debt
payments?”. `1.0×` is break-even; lenders price risk off the cushion above it. **Runway** answers “how long can
the treasury fund the current net burn?”, which matters for companies that are cash-flow negative even when
operating income is positive (capex-heavy growth).

### The rating corridor

Mathematics sets a **ceiling**; the LLM committee may only move the rating **down** from it.

| Tier | Ceiling requires | APR | Advance rate (of ARR) |
|------|------------------|-----|----------------------|
| AAA Prime | Runway ≥ 24 mo, DSCR ≥ 2.5×, ARR ≥ $1M | 4.00% | 40% |
| AA High Grade | Runway ≥ 18, DSCR ≥ 2.0×, ARR ≥ $500k | 6.00% | 35% |
| A Upper Medium | Runway ≥ 15, DSCR ≥ 1.5×, ARR ≥ $250k | 8.50% | 30% |
| BBB Investment Grade | Runway ≥ 12, DSCR ≥ 1.25× | 12.00% | 25% |
| BB Speculative | Runway ≥ 6, DSCR ≥ 1.0× | 18.00% | 15% |
| B High Risk | Runway ≥ 3 **or** DSCR ≥ 0.75× | 25.00% | 8% |
| C Substantial Risk | anything else with positive revenue | 35.00% | 4% |

* **Investment-grade floor.** Failing BBB's runway/DSCR bounds the rating strictly to BB/B/C.
* **Corroboration cap.** Revenue that on-chain inflows corroborate below 10% cannot be investment grade (≤ BB).
* **Credit limit** = `min(requested, ARR × advance_rate, 60% of pool assets)`.
* **Underwriting bond** = `max(0.1 GEN, 15% of requested limit)`, exact. A defaulter forfeits at least 15% of the line.
* **Global utilisation cap.** `total_borrowed + drawdown ≤ 60% × total_assets` for *every* borrower together
  (`ERR_POOL_CAP_REACHED`), so Sybil identities share one budget.
* **Absolute maturity.** The first drawdown fixes `loan_expiry = now + 365 d`; top-ups never extend it. The due date
  rolls at most to the maturity and the minimum instalment is `accrued + principal ÷ months_left`, so the debt
  amortises to zero by the terminal date. Past maturity the loan is delinquent.
* **Dynamic rate** = tier APR + a utilisation surcharge: 0 up to 80% pool utilisation, rising linearly to +500 bps
  at 100%. The rate is locked at assessment.
* **LLM notches.** The committee returns `CLEAN` or `SUSPICIOUS` and 0–2 notches *down* (`CLEAN` ≤ 1). The contract
  **recomputes the ceiling itself** from the agreed raw metrics, so no model output can lift a borrower above what
  the arithmetic allows. A model that cries `FRAUD` is demoted to “two notches down”; **only deterministic
  impossibility can slash a bond.**

### Interest, amortisation and LP yield

* Simple interest: `accrued += principal × rate_bps × Δt ÷ (10 000 × 31 536 000)`, accrued on every touch.
* Payments apply to interest first, then principal. A payment ≥ the minimum instalment
  (`accrued + ⌈principal ÷ 12⌉`) rolls the due date forward 30 days. Overpayments are refunded.
* **Interest split:** 90% raises LP net asset value; 10% funds the **insurance reserve**.
* **LP shares:** `shares = deposit × total_shares ÷ total_assets`. Interest raises `total_assets`, realised losses
  lower it, so the share price is monotonic under interest. `cumulative_yield_index` records LP interest per
  share (×1e18) as an ever-increasing audit metric. Blended LP APY = `Σ(principalᵢ × rateᵢ) × 0.9 ÷ total_assets`.
* **Loss waterfall on liquidation:** seized bond → insurance reserve → LP net asset value.

**Cash invariant** (checked in tests and on-chain via `solvent`):

```
contract balance == total_assets − total_borrowed + insurance_reserve + bonds_held
```

---

## 3. Architecture and data flow

```
 Borrower                         SynapseLiquid contract (GenVM)                       Validators (leader + N)
    │  apply_for_credit(bond)                │                                                  │
    ├──────────────────────────────────────►│ profile=PENDING, bond held as collateral         │
    │                                       │                                                  │
 Steward (anyone)                           │                                                  │
    │  assess_credit_consensus(borrower)    │                                                  │
    ├──────────────────────────────────────►│ run_nondet(leader_fn, validator_fn) ────────────►│
    │                                       │                         ┌────────────────────────┤
    │                                       │                         │ GET telemetry_uri      │
    │                                       │                         │ ├ 4xx/5xx/timeout ─────┼─► INCONCLUSIVE (fail closed)
    │                                       │                         │ ├ pre-flight (det.):   │
    │                                       │                         │ │  negative values,    │
    │                                       │                         │ │  burn < opex, dup tx,│
    │                                       │                         │ │  sha256 proof, ARR   │─► FRAUD  (impossible numbers)
    │                                       │                         │ ├ Runway/DSCR/ARR/ceil │
    │                                       │                         │ └ LLM committee        │
    │                                       │                         │    (0–2 notches DOWN)  │─► RATED
    │                                       │◄────────────────────────┴── leader result ───────┤
    │                                       │ validators re-run; agree iff outcome equal,      │
    │                                       │ metrics within 2%, notches within 1              │
    │                                       │ settle: recompute ceiling on-chain, clamp,       │
    │                                       │         rate = tier APR + utilisation surcharge  │
    │                                       │  RATED → ACTIVE   FRAUD → bond slashed + ban     │
    │                                       │  INCONCLUSIVE → bond refunded                    │
    │  drawdown_credit / service_debt       │                                                  │
    ├──────────────────────────────────────►│ accrue → split interest → LP NAV / reserve       │
    │                                       │                                                  │
 LP │  deposit_liquidity / withdraw_lp_capital (shares, pull-payment)                          │
    │                                       │  liquidate_borrower: bond → reserve → LPs        │
```

### Contract surface (`contracts/synapse_liquid.py`)

| Method | Kind | Purpose |
|--------|------|---------|
| `deposit_liquidity()` | payable | LP deposit, mints shares |
| `apply_for_credit(company_name, telemetry_uri, requested_limit)` | payable | exact `max(0.1 GEN, 15% of limit)` bond, public-https-only telemetry URI |
| `cancel_application()` | write | recover the bond of a `PENDING` application |
| `assess_credit_consensus(borrower)` | write | the consensus round above |
| `drawdown_credit(amount)` | write | borrow up to the rated limit and pool liquidity |
| `service_debt()` | payable | repay interest then principal; excess refunded |
| `withdraw_lp_capital(amount)` | write | pull-payment of principal + accrued yield (`0` = max) |
| `close_credit_line()` | write | debt-free borrowers recover the bond |
| `liquidate_borrower(borrower)` | write | permissionless after due date + 7-day grace |
| `freeze_borrower` / `unfreeze_borrower` / `set_usd_per_gen` / `transfer_governor` | governor | bounded controls |
| `get_credit_profile`, `get_pool_metrics`, `get_borrower_schedule`, `get_lp_position`, `get_rating_table`, `underwrite_preview` … | view | |

Statuses: `PENDING`, `ACTIVE`, `FROZEN`, `DEFAULTED` as specified, plus `INCONCLUSIVE` (fail-closed, bond
refunded, may re-apply), `REJECTED` (bond slashed, address banned) and `CLOSED`.

### Fraud and fail-closed rules

| Condition | Outcome |
|-----------|---------|
| `telemetry.borrower_address` ≠ the borrower being rated (or missing) | **revert `ERR_BORROWER_MISMATCH`**, no rating, no state change; applicant may `cancel_application()` |
| Any negative revenue / opex / burn / treasury (e.g. negative revenue while claiming AAA) | **FRAUD → bond slashed to insurance reserve, address banned** |
| `monthly_burn < monthly_opex` (outflows below operating costs) | FRAUD |
| Duplicate tx ids, non-positive amounts, malformed log | FRAUD |
| `proof_sha256` ≠ SHA-256 of the canonical transaction log, or log present without digest | FRAUD |
| `verified_onchain_inflows_usd` ≠ sum of the log | FRAUD |
| `claimed_arr_usd` off from 12 × revenue by > 2% | FRAUD |
| Feed unreachable, 404 / 4xx, 5xx / 429, malformed JSON, missing fields, zero revenue, > 64 KiB | **INCONCLUSIVE → bond refunded** |
| LLM returns non-JSON / errors | consensus rotation (`[LLM_ERROR]` never agrees) |

Proof digest: `sha256(json.dumps(transactions, sort_keys=True, separators=(",", ":")))` over the `transactions`
array. `scripts/make_telemetry.py` builds valid documents.

---

## 4. Tests, lint, build

```bash
uv venv --python 3.12 && uv pip install --prerelease=allow -r requirements.txt
.venv/bin/pytest tests/direct -q          # 289 in-memory GenVM tests (run files in parallel; ~100 s each)
.venv/bin/genvm-lint check contracts/synapse_liquid.py
cd frontend && npm install && npm run build   # tsc + vite, 0 errors
npm run console-check                          # headless Chrome: zero console errors on the live contract
```

The suite covers LP share/interest invariants, the AAA…C corridor at every threshold boundary, the 7-tier rate
table, LLM clamping and key aliasing, prompt-injection isolation, every fraud class and bond slash, every
fail-closed HTTP/parse path, accrual, amortisation, overpayment, closure, delinquency, the liquidation loss
waterfall, governor controls, and the shipped telemetry fixtures (`telemetry/*.json`). Direct mode runs the
leader function; validator agreement (`_results_agree`) is exercised by the validator-tolerance tests and live on
Studio Next.

---

## 5. Deployment and live seeding

```bash
.venv/bin/python scripts/make_telemetry.py          # regenerate telemetry/*.json with valid proofs
cd scripts
../.venv/bin/python deploy.py                       # keys → fund 10 GEN → deploy → seed 5 GEN
TELEMETRY_BASE_URL=https://<host>/telemetry ../.venv/bin/python interact_live.py seed
../.venv/bin/python interact_live.py assess-zeroproof   # the live steward review of Entity #3
../.venv/bin/python render_proofs.py                # refresh the proofs table above
```

* Keys are generated into `.env` (git-ignored, mode `600`): `DEPLOYER`, `AETHER`, `HYPERSCALE`, `ZEROPROOF`.
* Funding uses the `sim_fundAccount` RPC.
* **Hosting the telemetry feeds.** Validators fetch `telemetry_uri` server-side, so `telemetry/*.json` must be
  served over public https (for example a repository's `raw.githubusercontent.com` path). `interact_live.py`
  fetches each feed and verifies its proof digest *before* posting any bond.

| # | Entity | Telemetry | Resolved as |
|---|--------|-----------|-------------|
| 1 | Aether Infrastructure | ARR $2.5M, 28 mo runway, DSCR ≈ 3.8× | `AAA`, 4% APR, drawn down (expected) |
| 2 | HyperScale Labs | revenue $60k vs opex $180k, ≈ 2 mo runway | `C`, 35% APR, 0.115 GEN ceiling |
| 3 | ZeroProof Systems | ARR $960k, ≈ 22 mo runway | `PENDING` → live consensus (math ceiling `AA`) |

> **Status:** the audited contract is deployed and funded (section 1). The three positions above are **not yet seeded on
> chain**: seeding needs the (address-bound) telemetry feeds hosted at a public https URL, which has not been arranged;
> an attempt to publish them as a gist was blocked and not retried. The
> “Resolved as” column is what the shipped fixtures produce in the test suite (`test_telemetry_fixtures.py`), not
> an on-chain result. Run `interact_live.py seed` once `TELEMETRY_BASE_URL` is set.

---

## 6. Frontend (`frontend/`)

Vite + React + TypeScript + Tailwind, Lucide icons, `genlayer-js` (viem-based) for reads/writes, JetBrains Mono for
every figure. A 64 px single-line navbar (brand, pulsing “Studio Next • 61997”, explorer link, Connect Wallet);
Pool Health HUD; interactive rating-matrix yield curve; borrower registry as table or bento cards with glowing
rating badges and runway bars; the three-stage **Live Credit Assessment** modal (telemetry ingestion → ratio
extraction → rate settlement, with an audit console and the *Execute Validator Credit Assessment* button); and the
amortisation calculator. Reads need no wallet; writes use the injected EIP-1193 wallet with the Studio fee preset.

```bash
cd frontend && npm run dev      # http://localhost:5173  (syncs deployments/studio-next.json first)
```

---

## 7. Design boundaries & testnet threat model

### Audit findings and their fixes

| # | Severity | Finding | Fix (regression test) |
|---|----------|---------|-----------------------|
| 1 | Critical | Any address could submit another entity's public telemetry (e.g. `telemetry/aether.json`) and borrow against its rating | `borrower_address` is required in the telemetry and compared (case-insensitive) with the borrower inside the consensus round; mismatch reverts `ERR_BORROWER_MISMATCH` before any rating. (`test_foreign_telemetry_replay_rejected`) |
| 2 | Critical | Sybil addresses could each borrow within their own limit until the pool hit 100% utilisation | Hard cap `total_borrowed + drawdown ≤ 60% of total_assets`, `ERR_POOL_CAP_REACHED`. (`test_global_utilization_cap_enforced`) |
| 3 | High | Overdue loans kept nominal value in LP NAV, so early LPs could exit at par and leave the loss to the last LP | `get_total_assets()` marks every loan past its due date to 0; deposits/withdrawals/LP values use the marked-down NAV, so all holders share the loss pro rata; deposits are blocked while any loan is delinquent. (`test_delinquent_loan_bad_debt_haircut`, `test_early_exit_cannot_dump_loss_on_late_lp`) |
| 4a | Medium | A flat 0.1 GEN bond made large defaults profitable | bond = `max(0.1 GEN, 15% of limit)`. (`test_proportional_bond_scaling`) |
| 4b | Medium | Due dates could be rolled forward indefinitely | 12-month `loan_expiry`, due date clamped to it, instalments amortise toward it. (`test_absolute_maturity_enforced`) |
| 4c | Medium | SSRF via the telemetry URI | every IP literal (any spelling), localhost, `.local/.internal`, `nip.io`-style wildcard DNS, userinfo, IPv6 and cloud-metadata hosts are refused. (`test_ssrf_hosts_rejected`) |

### The off-chain oracle boundary (read this before trusting a rating)

This is a **testnet proof of concept**. Telemetry is a JSON document the borrower hosts; the contract does not (and
cannot) know whether the numbers are true. What the protocol does and does not establish:

* **Established on-chain:** the document names *this* borrower; it is internally consistent (proof digest, no
  duplicate/negative transactions, totals, ARR); every ratio is recomputed deterministically; validators agree on the
  same figures; the LLM can only lower the rating.
* **Not established:** that the revenue, treasury and transactions are real. `borrower_address` is a *self-asserted*
  binding, not a signature: whoever controls the hosted file can write any address into it, but a file served for
  borrower A cannot rate borrower B, and a self-consistent lie costs the liar a bond of ≥ 15% of the line.
* **Production path:** replace the self-asserted file with an attestation signed by a data provider or by the
  corporate key (the schema reserves room for an optional signature, currently ignored), verified in the validator
  round (`ecrecover`-style) against a registered signer; anchor inflows to verifiable on-chain transfers.

### Remaining limitations

* **Under-collateralised credit is real credit risk.** With a ≥ 15% bond, a default now costs the borrower the bond
  but still costs LPs the rest; the 60% pool cap, 60% concentration cap, ARR-linked advance rate, bad-debt haircut
  and the insurance reserve bound, not remove, that loss. Sybil identities each pay a ≥ 0.1 GEN bond.
* **The LLM committee** can only downgrade (≤ 2 notches); its worst case is a griefing downgrade, limited by the
  validator tolerance (within one notch) and leader rotation.
* **Governor** can freeze/unfreeze borrowers, set `usd_per_gen` (bounded) and rotate itself; it cannot move funds
  or change ratings.
* **O(borrowers) NAV.** The delinquency mark loops over all borrowers per LP call; fine for a PoC registry, a
  production pool would maintain an indexed delinquency set.
* **Re-rating** only for debt-free `ACTIVE` lines. Simple interest; 30-day periods; no early-repayment fees.
* **GEN/USD** is a governor-set notional (no oracle on a test network).
* **Native transfers** use `emit_transfer(on="finalized")` and settle after finalization.
* **Direct tests** run the leader path only; validator agreement is exercised live.

## 8. Repository

```
contracts/synapse_liquid.py   GenVM contract
tests/direct/                 pytest suite (in-memory GenVM)
scripts/                      deploy.py, interact_live.py, make_telemetry.py, render_proofs.py, lib.py
telemetry/                    borrower telemetry documents with valid proofs
deployments/studio-next.json  recorded address, source SHA-256, transaction hashes
frontend/                     Vite + React + Tailwind terminal, scripts/console-check.mjs
```

Author identity: SOBEK96 &lt;btcehsan@yahoo.com&gt;. License: MIT.
