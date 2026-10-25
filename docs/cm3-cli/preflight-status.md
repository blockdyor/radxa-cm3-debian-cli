# External preflight dispatch result

Inspected 2026-10-25 UTC. Source probe revision:
`f910df4b4e129d790a042402ac5e0e091de4b911` on `dev/cm3-debian-cli`.
Draft PR: https://github.com/blockdyor/radxa-cm3-debian-cli/pull/1

Status: BLOCKED BEFORE RUNNER ALLOCATION. No source package compilation,
complete signed package preflight or full-image attempt occurred. No artifact,
run URL or release exists for this attempted dispatch.

The actual command was:

    gh workflow run build.yaml --repo blockdyor/radxa-cm3-debian-cli \
      --ref dev/cm3-debian-cli \
      -f expected_sha=f910df4b4e129d790a042402ac5e0e091de4b911 \
      -f hypothesis='Initial pinned Trixie source-package feasibility probe'

GitHub returned HTTP 404: `workflow build.yaml not found on the default branch`.
A targeted `PUT actions/workflows/build.yaml/enable` also returned 404. Subsequent
readback established all of the following, not merely an inferred missing file:

- Authenticated repository permission includes push/admin.
- Repository Actions permissions reports `enabled: true`.
- The default-branch contents API returns `.github/workflows/build.yaml`, blob
  `a84ee8695cf8c18b552bd442837e0255825f332a` (inherited upstream workflow).
- Actions workflow registry returns `total_count: 0`, `workflows: []`.
- Specific workflow lookup returns 404; runs return `total_count: 0`.
- PR #1 is OPEN and draft, base `main`, head `dev/cm3-debian-cli` at the probe SHA.

Thus write access and file existence are verified, but a dispatchable workflow
registration is not. The precise GitHub-side cause is unknown. Do not describe
this as a compiler failure, a paid-runner requirement, or passed preflight.
Anonymous browser inspection also showed no workflows; no authenticated GitHub
browser session was available. No repository security/spending setting, default
branch, main-branch source or production state was changed.

## Minimum resume condition

An owner must make the reviewed manual workflow dispatchable in this fork, or
supply an authorized authenticated browser session for inspecting the fork's
workflow activation. If a default-branch registration/bootstrap commit is
required, approve that narrowly reviewed main-branch change first; this task is
scoped to the dedicated development branch and did not silently make it.

Do NOT blanket-enable inherited all-board/scheduled image builds or release
publication from the unchanged upstream main branch. Do not merge the entire
unfinished CLI experiment merely to register a workflow. Any bootstrap must
preserve manual-only execution, the fixed exclusive concurrency group, exact-SHA
assertion and no image/release stage. Once the workflow registry returns an actual
workflow ID, run the documented source-only probe against the then-approved
pushed development SHA, not a stale SHA.

After source success, finish the full signed ARM64 configuration/DKMS/update
preflight and secure CLI/boot implementation listed in `build.md`. Image assembly
remains explicitly disabled. All G0–G7 dispositions and all 28 UNTESTED hardware
rows remain unchanged. The three full-image attempts are still unused in the
inspected repository; check live phase-wide records again before any later run.
