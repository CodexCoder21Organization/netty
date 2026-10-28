# ARM download fix review

Date: 2026-10-28

## Scope and plan

Reviewed `fix/arm-toolchain-download-014730` (`ce4e8407d0dc8e8e244017ecfd5feff096e24014`) against `origin/4.2` (`006a2f1d92db733d10112de251600da7b6f8ec51`). The checked-out worktree is on `proof/w6-arm-download-014730`; branch files were read with `git show` as requested.

- Read root and Docker README files, the musl workflow, the aarch64 Dockerfile, compose arguments, and the candidate diff: **done**.
- Read the supplied testing guidance on reproducing defects, integration coverage, and comprehensive tests, plus the linked engineering guidance on root causes and end-to-end checks: **done**.
- Assess verification discrimination and coverage preservation: **done**.
- Assess code changes and record findings: **done**.

No code, tests, or builds were changed or run during this review. The only write is this review report.

## Verification and coverage review

**The proposed verification is well aimed at the reported defect.** The already-reproduced baseline failure on the exact CentOS 7 image, followed by a successful direct archive-host download in that image with normal TLS verification, distinguishes certificate-chain failure from a general network or server failure. Checking the downloaded archive against the pinned SHA-256 before extraction also means a successful toolchain install proves the bytes match the expected archive. The wrong-hash control should fail at that check; the original-URL reversal should fail at certificate verification. Together these controls would catch a removed checksum guard, an incorrect archive host, and an accidental TLS bypass.

Compiling and linking a small C program with the downloaded compiler, then checking its ELF machine type, verifies that this is a usable aarch64 compiler rather than merely a successful download and extraction. The real `build-jars-aarch64` job is still required to prove the existing Maven/QUIC build path works end to end.

**Build coverage is preserved in the candidate diff.** `docker/Dockerfile.cross_compile_aarch64` is the sole changed file. `.github/workflows/ci-verify-musl.yml` is byte-for-byte unchanged, including both architecture build legs and all five musl/glibc verification legs. The candidate does not skip or weaken any step. Its configured `gcc_version` remains `10.3-2021.07` in the Dockerfile and the CentOS 7 cross-compose file.

**Outstanding evidence:** this read-only review did not run the disposable proof or inspect a PR run. Record the actual results of the positive build, wrong-hash rejection, and URL-reversal control, and confirm the original `build-jars-aarch64` PR job passes on its first run before treating verification as complete. The plan should also record `aarch64-none-linux-gnu-gcc --version`; the candidate keeps the configured version and pins the archive, but an explicit version assertion makes that part of the proof visible alongside the ELF architecture assertion.

## Code review

No blocking code issue found.

- The candidate changes only the GCC archive URL and its download/install command. It points directly at the archive host supported by the supplied reproduction evidence, while leaving wget's certificate verification enabled.
- The SHA-256 check is part of the same `&&` chain and precedes `tar`, so a failed download or mismatched archive stops the Docker build before extraction.
- The default hash is a 64-character SHA-256 value for the pinned `10.3-2021.07` archive. The new build argument and Dockerfile comment explain that a different toolchain version needs its matching hash.
- The command uses `wget -nv`, so failures are no longer hidden by quiet mode. The existing GCC version, target path, `PATH`, and downstream build setup are unchanged.
- `git diff --check` reported no whitespace errors; the complete diff contains one file and six insertions/two deletions.

## Item-by-item result

- Review the relevant baseline and candidate files: **done**.
- Determine whether the proof discriminates the certificate defect: **done**; the positive and negative controls exercise distinct expected outcomes.
- Check for build-coverage reduction: **refuted**; the CI workflow and its architecture/musl matrices are unchanged.
- Review the Dockerfile change for correctness: **done**; no blocking issue found.
- Confirm actual proof and first-attempt PR CI results: **not part of this read-only review**; these remain required evidence for the parent task.
