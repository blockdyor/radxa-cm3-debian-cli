# External package preflight status

EXPERIMENTAL — NOT HARDWARE VALIDATED — NOT FOR PRODUCTION

Inspected 2026-10-28 UTC. Draft implementation PR:
https://github.com/blockdyor/radxa-cm3-debian-cli/pull/1

## Workflow repair (completed, not a package pass)

The historical HTTP 404 occurred despite a workflow blob existing on main:
Actions had no registered workflows. The precise GitHub-side cause was not
established. Focused bootstrap PR #3 promoted the reviewed manual package-only
workflow and guarded inherited automatic build/documentation/release jobs:
https://github.com/blockdyor/radxa-cm3-debian-cli/pull/3

Merged main commit: `133907e883a44a60d911fa8236b1e7e248be0d7d`.
Registered workflow: `396827381`, `build.yaml`, active. No account/repository
security policy or spending setting was relaxed. PR #1 was not merged.
Reversal: review a revert of bootstrap merge `133907e883a44a60d911fa8236b1e7e248be0d7d`
only after disabling the manual workflow and preserving inherited fork guards;
a blind revert would restore inherited automatic triggers and is unsafe.

## Package attempt 1 of 3 (failed)

Run: https://github.com/blockdyor/radxa-cm3-debian-cli/actions/runs/40294636804
Checked-out commit: `f531731036391073441cb4a3b770a5eb233ea807`, run attempt 1.
External runner: standard GitHub-hosted `ubuntu-24.04`. Checkout, policy checks
and resource qualification passed. U-Boot failed under GCC's retained
`-Werror=maybe-uninitialized`: `drivers/power/charge_animation.c:791` reported
`soc` and `current` potentially uninitialized. Kernel compilation was not reached.
The uploaded diagnostic artifact is `cm3-source-preflight-40294636804-1`.

The next source revision initializes only those two cached values to zero;
the existing mandatory first successful gauge poll and error checks remain.
It neither disables diagnostics nor changes source lineage/configuration.
Nested gitlink diffs are now recorded as well as recipe diffs so the exact
source patch is retained. Local patch-context/duplicate-application tests are
not a replacement for the actual external compile.

## Admission and remaining work

Package-only budget: initial attempt plus at most two evidence-based retries,
three total across operators/workflow reruns. The initial attempt is consumed;
no unchanged failing rerun is permitted. Before dispatch, reserve the next
attempt in the shared operational ledger and record its exact commit/hypothesis;
a concurrent or duplicate probe is prohibited. `attempts.json` records observed
runs, not an automatic atomic admission service.

A successful source compile is NOT full package preflight. Signed repository,
clean ARM64 configuration/update, real DKMS module and DTBO builds, exact boot
integration, secure enrollment and attested update verification remain pending.
Image assembly is disabled; no full-image attempt has run in the inspected
repository. Check the phase-wide ledger before any future image stage. Both
original gate definitions and all 28 UNTESTED hardware rows remain unchanged.
