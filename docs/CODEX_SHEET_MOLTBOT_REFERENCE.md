# CODEX_SHEET_MOLTBOT_REFERENCE.md
## Goal
Pull `moltbot/moltbot` into this repo as a pinned, read-only reference and pattern donor.
DO NOT merge its runtime into FRIDAY. Treat it as:
- a code-reading reference
- a pattern source (gateway/inbox/workspaces/skills architecture)
- a toolbox of ideas (not a dependency)

Primary outputs:
1) `vendor/moltbot_ref/` (pinned reference copy)
2) `docs/moltbot/` (notes + mapping doc + security threat model summary)
3) `docs/moltbot/EXTRACTED_PATTERNS.md` (what we will reimplement natively in FRIDAY)
4) `docs/moltbot/DO_NOT_IMPORT.md` (dangerous surfaces / what not to adopt)
5) `scripts/moltbot_ref/` (small helpers: grep, map generators)

Repo: https://github.com/moltbot/moltbot

---

## Hard Rules (must follow)
- Never execute Moltbot code as part of this import.
- Never run Moltbot containers/services.
- Never copy secrets/credentials patterns from Moltbot.
- Do not implement “skill downloading/marketplace” features.
- Do not expose any new ports or admin endpoints.
- Import is pinned to a commit and placed under `vendor/`.

---

## Approach Options
### Option A (Preferred): Git submodule (pinned reference)
Pros: pinned commit, clean updates, easy diff
Cons: requires submodule workflow

### Option B: Vendored snapshot (no submodules)
Pros: simplest operationally
Cons: larger repo, updates are manual

Default: Option A.

---

## Step 1 — Create directories
From repo root:
```bash
mkdir -p vendor
mkdir -p docs/moltbot
mkdir -p scripts/moltbot_ref
```

Step 2A — Add Moltbot as a submodule (preferred)
```bash
git submodule add https://github.com/moltbot/moltbot vendor/moltbot_ref
git submodule update --init --recursive
```

Pin a commit explicitly (optional but recommended):
```bash
cd vendor/moltbot_ref
git rev-parse HEAD > ../../docs/moltbot/MOLTBOT_PIN.txt
cd ../..
```

Add a guard note:

Create vendor/moltbot_ref/README_FRIDAY.md stating read-only reference and “do not run”.

Step 2B — Alternative: Vendored snapshot (no submodules)

If submodules are undesired:
```bash
git clone --depth 1 https://github.com/moltbot/moltbot vendor/moltbot_ref
rm -rf vendor/moltbot_ref/.git
echo "PINNED_SNAPSHOT=$(date -Iseconds)" > docs/moltbot/MOLTBOT_PIN.txt
```

Step 3 — Add a “DO NOT RUN” banner in our repo

Create docs/moltbot/README.md:

Purpose of the reference import

Pinned commit/hash

Security disclaimer: do not execute

What we plan to extract (gateway/inbox/skills/workspaces)

Step 4 — Generate a quick inventory of Moltbot (static scan only)

Create scripts/moltbot_ref/inventory.sh:
```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF="$ROOT/vendor/moltbot_ref"

if [[ ! -d "$REF" ]]; then
  echo "Missing vendor/moltbot_ref. Add it first." >&2
  exit 1
fi

OUT="$ROOT/docs/moltbot/INVENTORY.md"
echo "# Moltbot Reference Inventory" > "$OUT"
echo "" >> "$OUT"
echo "Generated: $(date -Iseconds)" >> "$OUT"
echo "" >> "$OUT"
echo "## Top-level files" >> "$OUT"
ls -la "$REF" >> "$OUT"
echo "" >> "$OUT"
echo "## Language / repo summary" >> "$OUT"
( cd "$REF" && find . -maxdepth 3 -type f | sed 's|^\./||' | head -n 400 ) >> "$OUT"
echo "" >> "$OUT"
echo "## Candidate architecture files (best-effort)" >> "$OUT"
( cd "$REF" && rg -n "gateway|inbox|skills|router|workspace|agent|policy|security" -S . | head -n 200 ) >> "$OUT"

echo "Wrote $OUT"
```

Make it executable:
```bash
chmod +x scripts/moltbot_ref/inventory.sh
```

Run it:
```bash
scripts/moltbot_ref/inventory.sh
```

Step 5 — Create mapping doc: Moltbot concepts → FRIDAY modules

Create docs/moltbot/MAPPING.md with this structure:

Moltbot "Gateway" → FRIDAY gateway/ (planned)

Moltbot "Inbox/Channels" → FRIDAY events/ + adapters (planned)

Moltbot "Skills" → FRIDAY skills/ loader (local-only)

Moltbot "Workspace isolation" → FRIDAY workspace_id keyed memory

Moltbot "Pairing/Allowlist" → FRIDAY trusted_senders list (planned)

Populate it with file pointers discovered by INVENTORY.md. Do not copy code yet; point to paths and summarize patterns.

Step 6 — Extract patterns as specs (not code)

Create docs/moltbot/EXTRACTED_PATTERNS.md:

For each pattern:

name

why it’s valuable

the trust boundary / threat model

FRIDAY-native design we will implement

minimal interfaces (Python types + endpoints)

what NOT to import

Start with 3 patterns:

Event model (MessageEvent/FileEvent/TickEvent)

Workspace routing and scoped memory/tool permissions

Skills format (SKILL.md metadata + local loader + allowlist)

Step 7 — Security “Do Not Import” list

Create docs/moltbot/DO_NOT_IMPORT.md:

Include:

any remote skill downloading / marketplace installation

any open inbound channel defaults (no pairing)

any exposed admin dashboards / management ports

any pattern that passes raw untrusted content into tool execution

any secrets stored in plaintext configs or logs

This is a guardrail checklist for future work.

Step 8 — Commit as a single atomic change

Stage:

submodule pointer OR vendored snapshot

docs/moltbot/*

scripts/moltbot_ref/*

Commit message:
ref: add moltbot as pinned reference + mapping/spec extraction scaffolding

Step 9 — Next implementation phase (not in this sheet)

After the reference import is done, start Phase 1.8:

implement FRIDAY-native gateway/ event router

implement local-only skills/ loader v1

add workspace routing policies

add audit log JSONL

All of these are FRIDAY-native; no Moltbot runtime is imported.


---

## What I’d do immediately after that sheet lands (so it stays “toolbox-only”)
- Add a repo-level note in `AGENTS.md`: **never execute code from `vendor/moltbot_ref`**
- Add a quick check script `scripts/check_no_vendor_imports.sh` that fails if Python imports from `vendor.moltbot_ref` (keeps it from accidentally becoming a dependency)

If you want, I’ll write that guard script too (tiny, very effective).
