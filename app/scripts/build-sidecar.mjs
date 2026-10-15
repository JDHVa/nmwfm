import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { exeSuffix, targetTriple } from "./triple.mjs";

const root = path.resolve(import.meta.dirname, "..", "..");
const triple = targetTriple();
const out = path.join(root, "app", "src-tauri", "binaries");
const work = path.join(root, "build", "pyinstaller");
const python = [
  path.join(root, ".venv", "Scripts", "python.exe"),
  path.join(root, ".venv", "bin", "python"),
].find(existsSync);

if (!python) {
  console.error("No se encontró el entorno virtual en .venv");
  process.exit(1);
}

mkdirSync(out, { recursive: true });
mkdirSync(work, { recursive: true });
const entry = path.join(work, "sidecar_entry.py");
writeFileSync(entry, "from backend.__main__ import main\n\nif __name__ == '__main__':\n    main()\n");

execFileSync(
  python,
  [
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--name",
    `nmwfm-backend-${triple}`,
    "--distpath",
    out,
    "--workpath",
    work,
    "--specpath",
    work,
    "--paths",
    root,
    entry,
  ],
  { cwd: root, stdio: "inherit" },
);

console.log(`Sidecar generado: ${path.join(out, `nmwfm-backend-${triple}${exeSuffix(triple)}`)}`);
