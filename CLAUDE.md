# vSAN Observability

Catalogs vSAN metrics and properties in VCF 9.1 twice, from the API and from Broadcom documentation, and compares them. Shared with collaborators through GitHub.

## Files

- Generated, do not edit by hand: `metrics-api.md`, `properties-api.md` (by `tools/build.py`); `metrics-docs.md`, `properties-docs.md`, `comparison.md` (by `tools/compare.py`). Change the scripts and regenerate.
- `tools/compare_notes.md`: the hand-written summary and findings inserted at the top of `comparison.md`. Update its numbers whenever the data changes.
- `raw/catalog.json` (live catalogs), `raw/schema.json` (pyVmomi type definitions), `raw/docs.json` (identifiers extracted from documentation).
- Object types and their order are defined once in `TYPES` and `ENTITY` in `tools/build.py`; `compare.py` reuses them.

## Rules

- No instance names, IP addresses, hostnames or values in the repo. The catalogs and schema contain none; keep it that way when collecting from a real vSAN cluster (field paths and counts only).
- Every API row names the method or entity type and field it comes from. Rows not seen with live values are marked *(schema)*.
- Documentation: extract names and identifiers only, never copy descriptions. Raw HTML stays in the git-ignored `.cache/`.
- Source codes: PERF, VSAN, VCPERF (API); KB, MAN, OPS, BLOG (documentation).

## Lab

- VCF 9.1 vCenter. Values (`VC_HOST`, `VC_USER`, `VCPW`) are in the git-ignored `.secrets/lab.env`; load with `. tools/env.ps1`. Scripts never hard-code them.
- The lab has **no vSAN cluster** (one 2-host cluster, VMFS and NFS only). The vSAN services on vCenter still answer catalog queries. When a vSAN cluster is available, add a collector that dumps field paths from the per-cluster query methods and replace *(schema)* marks with live evidence.
- Python: `.venv/` (git-ignored). PyPI downloads are blocked on this network; pyVmomi 9.1 was installed by copying `pyVmomi/`, `pyVim/`, `vsanapiutils.py` and `vsanmgmtObjects.py` from the GitHub release source into `.venv/Lib/site-packages`.

## Open items

- Verify *(schema)* fields against a live vSAN cluster (OSA and ESA).
- `ioinsight-histogram` and the `hr-*` real-time entity types are documented but not returned by `VsanPerfGetSupportedEntityTypes`; check them during an I/O Insight run and with real-time stats enabled.
- Health-check matching is by name; `OVERRIDE` in `tools/compare.py` holds manual pairs.
