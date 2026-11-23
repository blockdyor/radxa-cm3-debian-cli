# Retained image3 recovery attestation

EXPERIMENTAL/BETA — PHYSICAL HARDWARE UNTESTED — NOT FOR PRODUCTION

This is a new recovery/review statement, not a replacement original build
attestation. Producer run `41331537371`, attempt 1, built
`b71152296933808f99d7dc169fc6811861a9001b`: assembly succeeded, inspection failed
because the old verifier incorrectly required a UFS-only placement on MMC, and
the original provenance job was skipped. Those historical results remain intact.
Image3 uses the last of three permitted assemblies. This path never compiles,
assembles, changes image bytes, decrypts on a hosted runner or resets the ledger.

## Trust and statement

`project/cm3-cli/image3-recovery.json` freezes the reviewed local recovery
identities: original API ciphertext ZIP, CMS member, authenticated plaintext
manifest, exact raw/XZ, final corresponding sources/notices, package inventory,
independent review and source-repack record. No ciphertext or private key is
committed or uploaded. The independently executed checks and limitations are in
the named review report, whose digest is bound by that manifest.

The custom predicate type is:
`https://github.com/blockdyor/radxa-cm3-debian-cli/attestations/image-recovery/v1`.
Its predicate is the exact reviewed manifest plus `verificationSource`, the
new signing workflow's full commit. `hostedPayloadRehash=false` and
`originalBuildAttestationIssued=false` are mandatory. The hosted job verifies
committed policy and original GitHub run/artifact metadata, then signs the
approved subject digests using GitHub's OIDC/Sigstore service. It does not claim
to have replayed local decryption or payload checks. Signature validity does not
independently establish those local observations; trust also rests on reviewing
the committed policy and its bound evidence.

The source archive is separately repackaged without the dangling developer-only
`radxa-overlays/.pre-commit-config.yaml` absolute Nix link. The omission record
maps original and public archive identities; all other regular source files are
byte-preserved. Image raw/XZ bytes and original retained evidence are unchanged.
Do not extract original nested archives into a privileged or populated directory.

## Execute without building

At the independently reviewed exact source commit, dispatch existing `build.yaml`
on `dev/cm3-debian-cli` with all fields explicit:

    gh workflow run build.yaml --ref dev/cm3-debian-cli \
      -f expected_sha=FULL_REVIEWED_SIGNING_COMMIT \
      -f hypothesis=reviewed-image3-recovery-no-rebuild \
      -f recovery_only=true -f experimental_image=false -f public_distribution=false

The `packages` and original `provenance` jobs must be skipped. Only `recovery`
may run. Its permissions allow reading source/actions and issuing attestations,
not release or package writes. Failure is a failed recovery verification, not
permission to retry the producer or build a fourth image.

The signed subjects include raw, XZ, source/notices, package inventory, review,
source-repack record and review manifest. The run artifact contains public JSONL
signature, signed predicate, checksum list and hosted policy-test results only.
Download that artifact and copy the approved review manifest and subjects into a
local release-candidate directory. With this exact reviewed checkout and official
`gh` on PATH:

    python3 scripts/cm3-recovery-attestation.py verify \
      --approved-sha FULL_REVIEWED_SIGNING_COMMIT \
      --directory /path/to/candidate \
      --bundle /path/to/candidate/recovery-attestation.jsonl

The consumer hashes actual distributed materials, streams XZ expansion to check
the raw digest/size, verifies official signatures against the exact repository,
complete workflow certificate identity, signing/source commit, development ref,
GitHub OIDC issuer, custom predicate type and GitHub-hosted policy. It then compares
the authenticated predicate and whole subject set to the approved policy. Wrong
source, SLSA predicate substitution, tampered manifest/bytes or changed materials
must fail. It never weakens `cm3-verify-bundle.py`'s historical ciphertext policy.

## Publication boundary

A successful recovery attestation does not grant hardware, stable, production,
reproducibility or ongoing BSP update qualification. Hardware, retained BSP boot,
target systemd and active LSM stay UNTESTED. Historical image2 remains NO-PUBLISH.
Final independent candidate review and final checksum/readback precede publisher
handoff. GitHub prerelease/GHCR authority covers only the existing beta scope;
this workflow publishes neither release nor OCI package. A later OCI wrapper has
a different manifest digest and requires its own publisher readback/attestation;
never substitute the XZ digest for an OCI digest.
