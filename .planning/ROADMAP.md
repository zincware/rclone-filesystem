# Roadmap: rclone-filesystem v0.2

## Overview

This milestone transforms rclone-filesystem from a partially-working prototype into a fully compliant fsspec filesystem. The work proceeds layer by layer: path infrastructure first (everything depends on it), then file I/O contract compliance (the highest-impact single fix), then listing/caching (foundational for higher-level operations), then transfer operations (completing the API surface), and finally polish and ecosystem readiness. Each phase delivers a coherent, testable capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Path Infrastructure and Protocol Registration** - Centralized path handling, protocol attributes, entry_points, dependency bump, test fixture hardening (completed 2026-03-06)
- [ ] **Phase 2: File I/O Contract Fix** - Proper `_open()` implementation replacing `open()` override, text mode support
- [ ] **Phase 3: Listing, Metadata, and Caching** - `ls()` with FileNotFoundError, `info()`, DirCache integration, `cat_file()` optimization
- [ ] **Phase 4: Transfer Operations and Mutations** - `_put_file`, `_get_file`, `cp_file` fix, `mkdir`, `rmdir`, cache invalidation
- [ ] **Phase 5: Polish and Ecosystem Readiness** - Progress bars, CI rclone pinning

## Phase Details

### Phase 1: Path Infrastructure and Protocol Registration
**Goal**: Every method uses a single, validated path construction helper, and the filesystem is discoverable via `fsspec.filesystem("rclone")`
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, CONT-03, CONT-04, CONT-05, CONT-06, TEST-04, TEST-06, TEST-07, TEST-09
**Success Criteria** (what must be TRUE):
  1. All filesystem methods construct rclone paths through `_make_rclone_path()` -- no duplicated `f"{self.remote}:{path}"` patterns remain
  2. `fsspec.filesystem("rclone", remote="myremote:")` returns an `RCloneFileSystem` instance
  3. `RCloneFileSystem._strip_protocol("rclone://myremote:bucket/key")` returns the normalized path
  4. Paths containing shell metacharacters (`;`, `|`, `$`, etc.) raise `ValueError` before reaching rclone
  5. Test fixtures use dynamic port assignment and `monkeypatch` for environment variables
**Plans:** 3/3 plans complete

Plans:
- [ ] 01-01-PLAN.md -- Path helper, validation, builtins.open fix, dep bump, path tests
- [ ] 01-02-PLAN.md -- Protocol registration, _strip_protocol, _get_kwargs_from_urls, protocol tests
- [ ] 01-03-PLAN.md -- Test fixture hardening (dynamic port, monkeypatch, rclone-python API)

### Phase 2: File I/O Contract Fix
**Goal**: Users can read and write files through the standard fsspec `open()` interface, including text mode, without the library overriding fsspec's base class behavior
**Depends on**: Phase 1
**Requirements**: CONT-01, CONT-02, CORE-07, TEST-03, TEST-08
**Success Criteria** (what must be TRUE):
  1. `fs.open("path/file.txt", "rb")` returns a file-like object (not a context manager generator) that can be passed to any function expecting `IO[bytes]`
  2. `fs.open("path/file.txt", "r")` returns a text-mode wrapper that decodes bytes correctly
  3. Writing via `fs.open("path/file.txt", "wb")` uploads the file to the correct remote path (not a parent directory)
  4. The `RCloneFileSystem` class has no `open()` method override -- only `_open()`
**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md -- RCloneFile wrapper class, _open() implementation, contract tests
- [ ] 02-02-PLAN.md -- Text mode tests, write edge case tests

### Phase 3: Listing, Metadata, and Caching
**Goal**: Users get correct, cached directory listings and metadata, with proper error handling for non-existent paths
**Depends on**: Phase 2
**Requirements**: CONT-07, CORE-03, CORE-08, PERF-01, PERF-02, TEST-02
**Success Criteria** (what must be TRUE):
  1. `fs.ls("nonexistent/path")` raises `FileNotFoundError` (not returns empty list)
  2. `fs.info("path/file.txt")` returns a dict with name, size, and type without listing the entire parent directory
  3. Calling `fs.ls("path/")` twice in succession hits the DirCache on the second call (no second rclone subprocess)
  4. `fs.cat_file("path/file.txt")` retrieves content via `rclone.cat()` without creating a temp file
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Transfer Operations and Mutations
**Goal**: Users can efficiently upload, download, copy, and manage directories with correct file-to-file semantics and automatic cache invalidation
**Depends on**: Phase 3
**Requirements**: CORE-01, CORE-02, CORE-04, CORE-05, CORE-06, CORE-09, TEST-01, TEST-05, TEST-10
**Success Criteria** (what must be TRUE):
  1. `fs.put("local.txt", "remote/file.txt")` uploads the file to exactly `remote/file.txt` (not into `remote/file.txt/local.txt`)
  2. `fs.get("remote/file.txt", "local.txt")` downloads the file to `local.txt`
  3. `fs.cp_file("remote/a.txt", "remote/b.txt")` creates `b.txt` as a copy of `a.txt` (not `b.txt/a.txt`)
  4. `fs.mkdir("remote/newdir")` creates the directory and `fs.rmdir("remote/newdir")` removes it
  5. After any mutation operation (put, cp, rm, mkdir, rmdir), the DirCache for affected paths is invalidated
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Polish and Ecosystem Readiness
**Goal**: Transfer operations show progress feedback and CI uses a pinned rclone version for reproducible builds
**Depends on**: Phase 4
**Requirements**: PERF-03, CISC-01
**Success Criteria** (what must be TRUE):
  1. `fs.put("large.bin", "remote/large.bin", pbar=True)` displays a rich progress bar during upload
  2. CI workflow installs a specific pinned rclone version instead of curl-pipe-bash latest
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Path Infrastructure and Protocol Registration | 3/3 | Complete   | 2026-03-06 |
| 2. File I/O Contract Fix | 1/2 | Executing | - |
| 3. Listing, Metadata, and Caching | 0/? | Not started | - |
| 4. Transfer Operations and Mutations | 0/? | Not started | - |
| 5. Polish and Ecosystem Readiness | 0/? | Not started | - |
