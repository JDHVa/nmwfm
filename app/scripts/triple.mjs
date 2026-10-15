import { execFileSync } from "node:child_process";

export function targetTriple() {
  try {
    const out = execFileSync("rustc", ["-vV"], { encoding: "utf8" });
    const host = out.match(/^host:\s*(\S+)/m);
    if (host) return host[1];
  } catch {
    return "x86_64-pc-windows-msvc";
  }
  return "x86_64-pc-windows-msvc";
}

export function exeSuffix(triple) {
  return triple.includes("windows") ? ".exe" : "";
}
