# Milestones

## v0.2 fsspec Compliance (Shipped: 2026-03-06)

**Phases completed:** 5 phases, 11 plans
**Timeline:** 2025-06-10 to 2026-03-06
**Stats:** 58 files changed, +7,105 / -244 lines, 1,980 LOC Python
**Git range:** feat(01-01) to feat(05-01)

**Key accomplishments:**
1. Centralized path infrastructure with `_make_rclone_path()`, shell metacharacter validation, and fsspec protocol registration (`fsspec.filesystem("rclone")`)
2. Proper fsspec `_open()` contract via RCloneFile wrapper — enables text mode, compression, and transactions via base class delegation
3. DirCache-backed `ls()` with FileNotFoundError, `info()` with cache-first lookup, `cat_file()` via rclone cat, and pydantic-settings config layer
4. Complete transfer operations (`put_file`, `get_file`, `mkdir`, `rmdir`) with `copyto`-based `cp_file` fix and universal cache invalidation
5. Progress bar support (`show_progress`/`pbar`) wired through all transfer call sites with 3-tier resolution (kwarg > instance > settings/env)
6. CI hardened with rclone-bin PyPI package replacing curl-pipe-bash install

**Delivered:** A fully compliant fsspec filesystem where any rclone-supported remote works with `fs.open()`, `fs.put()`, `fs.get()`, `fs.ls()` — enabling pandas, xarray, dask integration via `storage_options`.

---

