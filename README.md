# SynapseLiquid

**Autonomous under-collateralised debt market and on-chain credit-rating protocol**, built on
[GenLayer](https://genlayer.com) Studio Next (chain `61997`).
Repository: <https://github.com/SOBEK96/SynapseLiquid>

> **Read [§7 Trust Model, Oracles & Testnet Threat Assumptions](#7-trust-model-oracles--testnet-threat-assumptions) before relying on any rating.**
> Telemetry here is self-asserted JSON on a test network, not an attested data source.

Web3 startups reporting cash flows (SaaS subscriptions, protocol fees, treasury inflows; **self-asserted** on this testnet, see §7) apply for
credit lines against a **proportional underwriting bond** (`max(0.1 GEN, 15% of the requested limit)`). GenVM validators fetch the applicant's JSON
telemetry, verify its self-consistency proof and structured financial telemetry, compute **Runway / DSCR / ARR** in integer arithmetic, and
reach multi-LLM consensus under the **Equivalence Principle** on a rating from `AAA` to `C`. The contract binds
the interest rate, credit limit and amortisation schedule directly to that rating.

> Studio Next is a test network. GEN has no market price here; fiat telemetry is converted at a governor-set
> notional (`usd_per_gen`, default $250,000). Nothing in this repository is investment advice.

---

## 1. Live on-chain proofs

<!-- PROOFS:START -->
- **Network:** GenLayer Studio Next · chain `61997` (`0xF22D`) · RPC `https://studio-next.genlayer.com/api`
- **Contract:** [`0x0d7A691c6280cccD6A1D9392d9Fd5f901dd3C5Bf`](https://explorer-studio-next.genlayer.com/address/0x0d7A691c6280cccD6A1D9392d9Fd5f901dd3C5Bf)
- **Source SHA-256 (`contracts/synapse_liquid.py`):** `2fca6116adcecf0b1d06768813b983a151ec1a5b0b94c2efc82a7e602836d790`
- **Runner:** `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`
- **Deployed:** 2026-10-01T14:53:42.250394+00:00
- **Superseded contract:** [`0x83709BEABCeC81C53fB776b37089Cdee976b3069`](https://explorer-studio-next.genlayer.com/address/0x83709BEABCeC81C53fB776b37089Cdee976b3069) — do not use
- **Superseded contract:** [`0xb4c01554C5C30ae3Cc706118460c7887E918650a`](https://explorer-studio-next.genlayer.com/address/0xb4c01554C5C30ae3Cc706118460c7887E918650a) — do not use
- **Superseded contract:** [`0x9A43e6660f9a4165F7BD5a911B15Dd2ae2381775`](https://explorer-studio-next.genlayer.com/address/0x9A43e6660f9a4165F7BD5a911B15Dd2ae2381775) — do not use

| # | Action | Transaction |
|---|--------|-------------|
| 1 | deploy | [`0xd0acca9a…43a0e3bf`](https://explorer-studio-next.genlayer.com/transactions/0xd0acca9aa33f2919fcb5619a33f824d94e3fa402befe78fa22437b7d43a0e3bf) |
| 2 | seed_liquidity 5.0 GEN | [`0xde4d6aae…5fb9a420`](https://explorer-studio-next.genlayer.com/transactions/0xde4d6aae78f01bdc4300fe3f2b15bdf36cee0c9fb282609ffb7015935fb9a420) |
| 3 | apply_for_credit Aether Infrastructure | [`0xb821533d…a1663dc4`](https://explorer-studio-next.genlayer.com/transactions/0xb821533df652e6ea873f2781d9f8e190322da2b3a191da5811be8884a1663dc4) |
| 4 | assess_credit_consensus Aether Infrastructure | [`0xcc40d1e4…7b47976c`](https://explorer-studio-next.genlayer.com/transactions/0xcc40d1e483986ebbc50d5176b04333fcd858858a34ade108851d09817b47976c) |
| 5 | apply_for_credit HyperScale Labs | [`0x5a2a138f…f4613d78`](https://explorer-studio-next.genlayer.com/transactions/0x5a2a138fe7468b0742fb578276a0793bc29a4e565bf8438ea14af5b1f4613d78) |
| 6 | assess_credit_consensus HyperScale Labs | [`0x34e3bda9…ed1d7c8c`](https://explorer-studio-next.genlayer.com/transactions/0x34e3bda9d1d2e1f5ced4717e3f753270d5784f73fe7598a3a2bb0bcced1d7c8c) |
| 7 | apply_for_credit ZeroProof Systems | [`0x946dfafc…898edfbe`](https://explorer-studio-next.genlayer.com/transactions/0x946dfafc5d6ce89bbc8a8ab91ad74bcc81d104473220fc7e6e22fd84898edfbe) |
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
* **Drawdown cooldown.** No drawdown until 24 h after the assessment (`ERR_COOLDOWN_ACTIVE`); a re-assessment
  restarts it. Telemetry cannot be cashed out in the same breath it was produced.
* **Tranche cap and time-lock.** At most 50% of the approved limit may be outstanding until (a) the borrower has paid
  one on-time installment (`ERR_TRANCHE_CAP`) **and** (b) one full 30-day payment cycle has elapsed since the first
  drawdown (`ERR_TRANCHE_COOLDOWN_ACTIVE`). Paying a token installment seconds after drawing does not unlock tranche 2.
* **Dust floor.** Every drawdown is ≥ 0.5 GEN (`ERR_DRAWDOWN_TOO_SMALL`), except the draw that exactly exhausts an
  open line's headroom. With the 50% first tranche this makes 1 GEN the smallest usable line.
* **Post-liquidation pause.** A liquidation of ≥ 10% of pool assets pauses all new drawdowns for 72 h
  (`ERR_POOL_PAUSED`); repayments and LP exits stay open.
* **Bounded loops.** NAV/delinquency walk a registry of borrowers with debt outstanding (swap-remove, O(1) updates),
  capped at 64 simultaneous borrowers (`ERR_ACTIVE_BORROWER_CAP`). A borrower is evicted from the set the moment its
  principal reaches zero; empty, pending or cancelled applications are never iterated.
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
| `drawdown_credit(amount)` | write | after the 24 h cooldown; ≤ 50% of the limit until an installment is paid; subject to the 60% pool cap, pause and active-set bound |
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
.venv/bin/pytest tests/direct -q          # 312 in-memory GenVM tests (run the files as parallel pytest processes; ~100 s each)
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
../.venv/bin/python interact_live.py seed                # again after 24 h: Aether's first-tranche drawdown (cooldown)
../.venv/bin/python interact_live.py assess-zeroproof   # the live steward review of Entity #3
../.venv/bin/python render_proofs.py                # refresh the proofs table above
```

* Keys are generated into `.env` (git-ignored, mode `600`): `DEPLOYER`, `AETHER`, `HYPERSCALE`, `ZEROPROOF`.
* Funding uses the `sim_fundAccount` RPC.
* **Hosting the telemetry feeds.** Validators fetch `telemetry_uri` server-side, so `telemetry/*.json` must be
  served over public https (for example `https://raw.githubusercontent.com/SOBEK96/SynapseLiquid/main/telemetry`). `interact_live.py`
  fetches each feed and verifies its proof digest *before* posting any bond.

| # | Entity | Telemetry | Resolved as |
|---|--------|-----------|-------------|
| 1 | Aether Infrastructure | ARR $2.5M, 28 mo runway, DSCR ≈ 3.8× | **`AAA`, 4% APR (live)**; first tranche (≤ 50% of limit) opens after the 24 h cooldown |
| 2 | HyperScale Labs | revenue $60k vs opex $180k, ≈ 2 mo runway | **`C`, 35% APR, 0.115 GEN ceiling (live)** |
| 3 | ZeroProof Systems | ARR $960k, ≈ 22 mo runway | `PENDING` → live consensus (math ceiling `AA`) |

> **Live status.** On the current contract, validators fetched the address-bound feeds from
> `raw.githubusercontent.com/SOBEK96/SynapseLiquid/main/telemetry` and reached consensus: **Aether `AAA` (4.00% APR,
> DSCR 3.82×, 28 mo runway, 3.0 GEN limit)** and **HyperScale `C` (35.00% APR, DSCR 0, 0.1152 GEN limit)** are
> `ACTIVE`; **ZeroProof is `PENDING`** for the live steward review (`interact_live.py assess-zeroproof`). Aether's
> first-tranche drawdown is **not yet executed**: the mandatory 24 h cooldown after assessment ends
> 2026-10-02 14:55 UTC, after which `interact_live.py seed` draws it (≤ 1.5 GEN, the 50% tranche). HyperScale's line is
> below the 0.5 GEN drawdown floor, so it can be rated but never drawn. The transactions are in the table in section 1.

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

## 7. Trust Model, Oracles & Testnet Threat Assumptions

**Telemetry is self-asserted.** The `telemetry/*.json` documents are JSON feeds that a borrower (here: this
repository's author) hosts at a URL and that GenVM validators fetch independently. They exist to **exercise
multi-validator consensus on Studio Next** — fetching, deterministic pre-flight, ratio extraction, LLM review,
equivalence agreement. Nothing in them is cryptographically attested. The contract proves that the document
*names this borrower*, is *internally consistent*, and that *validators derived the same numbers*; it cannot prove
the revenue, treasury or transactions are real. `borrower_address` is a self-asserted binding, not a signature.
Do not read a rating issued here as evidence of anyone's creditworthiness.

**Production would not accept unconstrained self-submitted URLs.** A production deployment must replace the
self-hosted file with data whose origin a validator can verify cryptographically, for example:

* **TLSNotary / zkTLS proofs** of an HTTPS session with the payment processor, bank or accounting API;
* **verifiable credentials** issued by the data source (e.g. a Stripe-issued revenue credential);
* **signed reports from an authorised on-chain oracle signer** registered in the contract, verified inside the
  validator round (`ecrecover`-style), with signer rotation and revocation;
* inflows anchored to **verifiable on-chain transfers** rather than an uploaded log.

The schema leaves room for an optional corporate signature (currently ignored) so such attestations can be added
without changing the rating logic.

### Active mitigations (what bounds the damage while telemetry is unattested)

| Control | Parameter | Stops |
|---------|-----------|-------|
| Identity binding | `borrower_address` must equal the rated address (`ERR_BORROWER_MISMATCH`) | replaying someone else's public file |
| Global utilisation cap | `total_borrowed ≤ 60%` of pool assets, all borrowers combined (`ERR_POOL_CAP_REACHED`) | Sybil swarms draining to 100% |
| Dynamic bond | `max(0.1 GEN, 15%)` of the requested limit | profitable defaults / cheap identities |
| Absolute maturity | 12 months from first drawdown, due date clamped, instalments amortise to it | endless rollovers |
| Bad-debt haircut | loans past due are marked to 0 in LP NAV; deposits blocked while delinquent | early-exit-at-par, loss dumped on the last LP |
| Drawdown cooldown | 24 h from assessment to first drawdown | cash-out of freshly self-generated telemetry |
| Tranche cap + time-lock | ≤ 50% of the limit until an installment is paid *and* 30 days after the first drawdown | extracting the whole line in one transaction, or bumping `installments_paid` with a token payment |
| Dust floor + eviction | drawdown ≥ 0.5 GEN; slot freed when debt is zero | squatting the 64 slots with dust loans |
| Post-liquidation pause | 72 h pool-wide drawdown pause after a liquidation of ≥ 10% of assets | recycling freed liquidity to the next Sybil |
| Active-borrower registry | NAV loop over indebted borrowers only, ≤ 64 | gas DoS via empty/cancelled applications |
| SSRF-hardened URI | public https DNS names only; every IP literal, localhost, `.internal/.local`, wildcard DNS, userinfo, IPv6, metadata hosts refused | validators being aimed at internal services |
| Deterministic fraud rules | impossible numbers slash the bond; the LLM can only lower a rating (≤ 2 notches) | model-driven confiscation or inflation |

### Audit trail

| Finding | Severity | Resolution (test) |
|---------|----------|-------------------|
| Foreign telemetry replay | Critical | identity binding (`test_foreign_telemetry_replay_rejected`) |
| Sybil drain to 100% utilisation | Critical | 60% global cap (`test_global_utilization_cap_enforced`) |
| Delinquent loans at par in NAV | High | haircut (`test_delinquent_loan_bad_debt_haircut`) |
| Sequential Sybil extraction / instant cash-out | High | cooldown, tranche cap, pause (`test_cooldown_blocks_immediate_drawdown`, `test_first_tranche_capped_at_half_the_limit`, `test_major_liquidation_pauses_new_drawdowns`) |
| Flat bond; rollovers; SSRF | Medium | proportional bond, absolute maturity, hardened URI (`test_proportional_bond_scaling`, `test_absolute_maturity_enforced`, `test_ssrf_hosts_rejected`) |
| Linear borrower scan in NAV | Medium | active-borrower registry, bounded set (`test_registry_*`, `test_active_borrower_set_is_hard_bounded`) |
| Tranche-2 bypass via token installment | High | 30-day tranche time-lock (`test_tranche_two_blocked_for_a_full_cycle_after_first_drawdown`) |
| Registry slot squatting with dust loans | Medium | 0.5 GEN floor + immediate eviction (`test_dust_drawdown_is_refused`, `test_borrower_evicted_the_moment_debt_hits_zero`) |

### Residual risk and limitations

* **A self-consistent lie is not detectable on-chain.** The controls above cap how much a liar can take and make it
  cost a bond; they do not make telemetry true. Under-collateralised lending remains real credit risk for LPs.
* **Pause and cap are blunt.** A single large borrower can still trigger a pause; the 64-borrower bound is a PoC
  limit, not a scalability claim. A well-funded attacker can still occupy slots with 0.5 GEN loans (each also costs a
  bond of ≥ 0.1 GEN and a 24 h wait); the floor raises the price, it does not remove the attack.
* **The LLM committee** can only downgrade; its worst case is griefing, limited by validator tolerance and rotation.
* **Governor** (the deployer) can freeze/unfreeze borrowers, set `usd_per_gen` (bounded) and rotate itself; it cannot
  move funds or change ratings.
* **Re-rating** only for debt-free `ACTIVE` lines. Simple interest, 30-day periods, no early-repayment fees.
* **GEN/USD** is a governor-set notional (no oracle on a test network).
* **Native transfers** use `emit_transfer(on="finalized")` and settle after finalization.
* **Direct tests** run the leader path only; validator agreement is exercised live.

---

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
