import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { exeSuffix, targetTriple } from "./triple.mjs";

const triple = targetTriple();
const dir = path.resolve(import.meta.dirname, "..", "src-tauri", "binaries");
const file = path.join(dir, `nmwfm-backend-${triple}${exeSuffix(triple)}`);

if (!existsSync(file)) {
  mkdirSync(dir, { recursive: true });
  copyFileSync(process.execPath, file);
  console.log(`Sidecar de relleno creado: ${file}`);
}
