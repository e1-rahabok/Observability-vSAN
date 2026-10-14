## Summary

| Area | API | Documentation | Gap |
|---|---|---|---|
| Performance metrics | 1,164 metrics in 69 entity types, listed live | 386 metric IDs in 2 KBs; the VCF 9.1 manual names chart groups only | 840 live metrics (72%) are not documented; 44 of 69 entity types have no KB coverage at all |
| Health checks | 191 checks (181 distinct test IDs), listed live | 139 entries in the KB index | 71 test IDs have no KB entry; 30 KB entries match no live check |
| Capacity | 59 fields in `VsanQuerySpaceUsage` (schema) | 2 manual pages (legacy and ESA effective capacity) | Most terms map to a field; a few are UI calculations |
| Configuration and inventory | About 1,390 property fields (schema) | VCF Operations lists 68 properties | The documentation covers a small fraction |

## Findings

1. **Most performance metrics are undocumented.** The KBs cover the classic charts (cluster, host, disk group, disk, network, VM, iSCSI, file service, I/O Insight). Whole areas returned live have no documentation with API IDs: ESA global deduplication (10 entity types, 266 metrics), DOM owner, resync, RDT network latency, CMMDS, vSAN CPU and memory overhead, PMem, vSAN Direct, sparse host, CLOM and dying-disk handling.
2. **Documented IDs that the live API does not list.** `ioinsight-histogram` (30 histogram buckets, read and write) is documented as an entity type but is not returned by `VsanPerfGetSupportedEntityTypes`; it may exist only while an I/O Insight run is active. `vsan-host-net` `tcpTxRexmitRate` and `tcpRxErrRate` are documented, but the live entity lists `ioChainRxdrops` and `ioChainTxdrops` instead, and TCP statistics are in a separate `vsan-tcpip-stats` entity.
3. **Errors in the KBs.** KB 326812 gives the Remote VM latency charts the throughput IDs (`throughputRead`, `throughputWrite`); the live API has `latencyAvgRead` and `latencyAvgWrite` for those entities. It also titles the ESA disk-layer read latency (`avgLatReadCapacity`) "Read IOPS". KB 326812 writes the remote client entity types as "A or B"; the API has them as separate entity types.
4. **Real-time entity types cannot be discovered.** The KBs name `hr-*` real-time entity types (30-second samples, 7-day retention, vSAN 8.0 U1 and later). `VsanPerfGetSupportedEntityTypes` does not return them.
5. **Health catalog quirks.** Ten checks are listed twice, in a local group and in "Online health" (`cloudhealth`), with the same test ID. 19 checks return an untranslated message key (`com.vmware.vsan.health.test…testname`) instead of a name.
6. **Capacity: the documentation and the API use different names.** "Total usable capacity" is `effectiveSpaceUsage.totalUsableB`, "Object reserved" is `overReservedB`, "Data reduction ratio" is `spaceEfficiencyRatio.overallRatio`. "Used capacity", "Overprovisioning ratio" and "RAID factor" have no field of their own; the UI computes them.
7. **VCF Operations is a third vocabulary.** Its keys (for example `vSAN|Disk Space|Disk Space Used (%)`) do not name the vSAN API field behind them. It has no vSAN metrics for network adapters, objects, VMs, virtual disks or iSCSI.

## Limits of this comparison

- The lab has no vSAN cluster. Performance metrics and health checks are live catalogs from the vSAN service; every other API field comes from the pyVmomi 9.1 type definitions and was not seen with values.
- Health checks are matched by name, plus the manual overrides listed in `tools/compare.py`. The counts are approximate.
- KB articles carry no version; they were read on the date of the commit.
