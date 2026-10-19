# vSAN Observability

Catalogs vSAN metrics and properties in VCF 9.1 twice, from the API and from Broadcom documentation, and compares them. Shared with collaborators through GitHub.

## Files

- Generated, do not edit by hand: `metrics-api.md`, `properties-api.md`, `internal-api.md` (by `tools/build.py`); `metrics-docs.md`, `properties-docs.md`, `comparison.md` (by `tools/compare.py`). Change the scripts and regenerate.
- `tools/compare_notes.md`: the hand-written summary and findings inserted at the top of `comparison.md`. Update its numbers whenever the data changes.
- `raw/catalog.json` (live catalogs), `raw/schema.json` (pyVmomi type definitions), `raw/live.json` (field paths, metric labels and counts seen on a live vSAN cluster, by `tools/live.py`), `raw/docs.json` (identifiers extracted from documentation).
- Object types and their order are defined once in `TYPES` and `ENTITY` in `tools/build.py`; `compare.py` reuses them.

## Rules

- No instance names, IP addresses, hostnames or values in the repo. The catalogs and schema contain none; keep it that way when collecting from a real vSAN cluster (field paths and counts only).
- Every API row names the method or entity type and field it comes from. Rows not seen with live values are marked *(schema)*.
- Documentation: extract names and identifiers only, never copy descriptions. Raw HTML stays in the git-ignored `.cache/`.
- Source codes: PERF, VSAN, VCPERF, VIM, VSANINT (API; VSANINT = host `VsanInternalSystem`, only in `internal-api.md`); KB, MAN, OPS, BLOG (documentation).
- `tools/live.py` refuses to write `raw/live.json` if any cluster, host, datastore or VM name appears in it (names that are ordinary API words are allowed). It never calls methods that start tests, generate load or change configuration.

## Lab

- Two vCenters. Values (`VC_HOST`, `VC_USER`, `VCPW`) are in git-ignored files under `.secrets/`; load with `. tools/env.ps1` (lab) or `. tools/env.ps1 live`. Scripts never hard-code them.
- `lab`: VCF 9.1.0, **no vSAN cluster** (VMFS and NFS only); used for the catalogs (`catalog.py`).
- `live`: VCF 9.1.1, one OSA vSAN cluster (3 hosts, performance service on, verbose mode off, no dedup, encryption, file service, iSCSI or stretched). Read-only account. Used by `live.py`.
- Python: `.venv/` (git-ignored). PyPI downloads are blocked on this network; pyVmomi 9.1 was installed by copying `pyVmomi/`, `pyVim/`, `vsanapiutils.py` and `vsanmgmtObjects.py` from the GitHub release source into `.venv/Lib/site-packages`.

## Open items

- Remaining *(schema)* fields need an ESA cluster and clusters with dedup, encryption, file service, iSCSI, stretched/2-node; perf verbose mode would fill the verbose-only entity types (world CPU, slab and heap memory, CLOM, CMMDS workload, TCP/IP).
- Calls that still fail on the live cluster: `VsanQueryPhysicalPlacements`, `VsanGetHclConstraints`, `VsanQueryEntitySpaceUsage` (see `raw/live.json` errors).
- `ioinsight-histogram` and the `hr-*` real-time entity types are documented but not returned by `VsanPerfGetSupportedEntityTypes`; check them during an I/O Insight run and with real-time stats enabled.
- Health-check matching is by name; `OVERRIDE` in `tools/compare.py` holds manual pairs.
- Planned: a nested (virtual ESXi) lab to cover ESA, dedup, encryption, file service, iSCSI, stretched/2-node and verbose mode. Field paths and metric names are the same as on physical hosts, but hardware-sourced fields (disk/controller vendor, model, firmware, SMART, HCL, pNIC/RDMA) are virtual or empty there. Before using it: have `live.py` record `"nested": true` (when the host model is a VMware virtual platform, without storing the model string), and have `compare.py` mark hardware rows seen only on nested hosts. Note that `paths()` in `tools/lab.py` counts `""` and `0` as seen. Keep the physical OSA cluster as the reference for hardware fields.
