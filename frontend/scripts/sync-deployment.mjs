// Copies deployments/studio-next.json into src/deployment.json so the bundle
// knows the live contract address. Writes an empty record when none exists yet
// (the UI then shows a "no deployment" state instead of failing).
import { copyFileSync, existsSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../deployments/studio-next.json");
const dst = resolve(here, "../src/deployment.json");
if (existsSync(src)) copyFileSync(src, dst);
else writeFileSync(dst, "{}\n");
console.log(existsSync(src) ? "deployment.json synced" : "no deployment recorded; wrote empty deployment.json");
