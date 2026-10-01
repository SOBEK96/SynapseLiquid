// Chain access: account-less reads through genlayer-js, wallet writes through
// the injected EIP-1193 provider. All reads degrade to `null`, never throw into
// the render path, and never log: the console stays clean when the RPC is slow.
import { createClient, chains } from "genlayer-js";
import deployment from "../deployment.json";

export const CHAIN_ID = 61997;
export const CHAIN_HEX = "0xF22D";
export const RPC_URL = "https://studio-next.genlayer.com/api";
export const EXPLORER = "https://explorer-studio-next.genlayer.com";

interface Deployment {
  contract_address?: string;
  source_sha256_at_record?: string;
  transactions?: { label: string; hash: string; url: string }[];
}
const dep = deployment as Deployment;

export const CONTRACT: string | undefined =
  (import.meta.env.VITE_CONTRACT_ADDRESS as string | undefined) || dep.contract_address;
export const DEPLOYMENT = dep;
export const explorerAddress = (a: string) => `${EXPLORER}/address/${a}`;
export const explorerTx = (h: string) => `${EXPLORER}/transactions/${h}`;

export interface Pool {
  total_deposited: string;
  lp_nav?: string;
  delinquent_principal?: string;
  available_liquidity: string;
  borrowed_liquidity: string;
  utilization_bps: number;
  lp_apy_bps: number;
  insurance_reserve: string;
  bonds_held: string;
  total_interest_paid: string;
  default_rate_bps: number;
  borrower_count: number;
  usd_per_gen: number;
  cumulative_originated: string;
  cumulative_defaulted: string;
  cumulative_yield_index: string;
}

export interface Profile {
  borrower: string;
  company_name: string;
  metadata_uri: string;
  underwriting_bond: string;
  rating: string;
  rating_label: string;
  credit_limit: string;
  borrowed_amount: string;
  interest_rate_bps: number;
  dscr_ratio: number;
  monthly_revenue_usd: number;
  burn_rate_usd: number;
  runway_months: number;
  arr_usd: number;
  last_assessment_timestamp: number;
  status: string;
  requested_limit: string;
  assessment_reason: string;
  applied_at: number;
}

export interface Schedule {
  principal: string;
  accrued_interest: string;
  total_owed: string;
  repayment_due: number;
  minimum_payment: string;
  total_repaid: string;
  overdue: boolean;
  liquidatable: boolean;
}

export interface Snapshot {
  pool: Pool;
  borrowers: Profile[];
  schedules: Record<string, Schedule>;
  at: number;
}

// genlayer-js returns Map for dict values; normalise recursively.
function plain(v: unknown): unknown {
  if (v instanceof Map) return Object.fromEntries([...v.entries()].map(([k, x]) => [String(k), plain(x)]));
  if (Array.isArray(v)) return v.map(plain);
  if (typeof v === "bigint") return v.toString();
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plain(x)]));
  return v;
}

type AnyClient = {
  readContract: (a: { address: string; functionName: string; args?: unknown[] }) => Promise<unknown>;
  writeContract: (a: Record<string, unknown>) => Promise<string>;
  estimateTransactionFees: (a: Record<string, unknown>) => Promise<Record<string, unknown>>;
  waitForTransactionReceipt: (a: Record<string, unknown>) => Promise<Record<string, unknown>>;
  getTransaction: (a: { hash: string }) => Promise<Record<string, unknown>>;
};

const sdkChain = () => ({
  ...(chains.studioDevnet as object),
  rpcUrls: { default: { http: [RPC_URL] } },
});

let reader: AnyClient | null = null;
function readClient(): AnyClient {
  if (!reader) reader = createClient({ chain: sdkChain() as never }) as unknown as AnyClient;
  return reader;
}

export async function read<T>(fn: string, args: unknown[] = []): Promise<T | null> {
  if (!CONTRACT) return null;
  try {
    const r = await readClient().readContract({ address: CONTRACT, functionName: fn, args });
    return plain(r) as T;
  } catch {
    return null;
  }
}

export async function loadSnapshot(): Promise<Snapshot | null> {
  const pool = await read<Pool>("get_pool_metrics");
  if (!pool) return null;
  const borrowers: Profile[] = [];
  const schedules: Record<string, Schedule> = {};
  for (let i = 0; i < pool.borrower_count; i++) {
    const key = await read<string>("get_borrower_at", [i]);
    if (!key) continue;
    const p = await read<Profile>("get_credit_profile", [key]);
    if (!p) continue;
    borrowers.push(p);
    const s = await read<Schedule>("get_borrower_schedule", [key]);
    if (s) schedules[key.toLowerCase()] = s;
  }
  return { pool, borrowers, schedules, at: Date.now() };
}

// ------------------------------------------------------------------- wallet
export interface Eip1193 {
  request: (a: { method: string; params?: unknown[] }) => Promise<unknown>;
}
export const injected = (): Eip1193 | undefined =>
  (window as unknown as { ethereum?: Eip1193 }).ethereum;

export async function connectWallet(): Promise<string> {
  const eth = injected();
  if (!eth) throw new Error("No injected wallet found. Install an EIP-1193 wallet (e.g. MetaMask).");
  const accounts = (await eth.request({ method: "eth_requestAccounts" })) as string[];
  const current = (await eth.request({ method: "eth_chainId" })) as string;
  if (parseInt(current, 16) !== CHAIN_ID) {
    try {
      await eth.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
    } catch {
      await eth.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: CHAIN_HEX,
            chainName: "GenLayer Studio Next",
            nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
            rpcUrls: [RPC_URL],
            blockExplorerUrls: [EXPLORER],
          },
        ],
      });
    }
  }
  return accounts[0];
}

export interface WriteResult {
  hash: string;
  status: string;
}

export async function write(
  account: string,
  method: string,
  args: unknown[] = [],
  valueWei = 0n,
  onHash?: (h: string) => void,
): Promise<WriteResult> {
  const eth = injected();
  if (!CONTRACT) throw new Error("No contract deployed");
  if (!eth) throw new Error("No injected wallet");
  const client = createClient({ chain: sdkChain() as never, account: account as never, provider: eth as never }) as unknown as AnyClient;
  const fees = await client.estimateTransactionFees({});
  const hash = await client.writeContract({
    address: CONTRACT,
    functionName: method,
    args,
    value: valueWei,
    fees,
  });
  onHash?.(hash);
  const receipt = await client.waitForTransactionReceipt({ hash, status: "ACCEPTED", retries: 150, interval: 4000 });
  return { hash, status: String(receipt.statusName ?? receipt.status ?? "ACCEPTED") };
}
