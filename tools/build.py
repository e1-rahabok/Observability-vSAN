# Generates metrics-api.md and properties-api.md from raw/catalog.json (live) and raw/schema.json (type definitions).
# Re-run after tools/catalog.py or tools/schema.py:  python tools/build.py
import os, re, json

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
cat = json.load(open(os.path.join(ROOT, "raw", "catalog.json")))
sch = json.load(open(os.path.join(ROOT, "raw", "schema.json")))

TYPES = ["vSAN Cluster", "vSAN Datastore", "vSAN Host", "Disk Group", "vSAN Disk", "vSAN Network Adapter",
         "vSAN Object", "Virtual Machine", "Virtual Disk", "File Share", "iSCSI Target", "iSCSI LUN"]

# --- performance service entity types -> object type
ENTITY = {
    "vSAN Cluster": "cluster-domclient cluster-domcompmgr cluster-domowner cluster-resync vsan-cluster-capacity "
                    "cluster-rdt-network-latency cluster-remotedomclient computeCluster-remotedomclient vsan-direct-cluster "
                    "cluster-zdom-top-stats cluster-pmem cluster-esa-dedup-store-chunksvc cluster-esa-dedup-store-hashsvc "
                    "cluster-esa-dedup-domowner-io cluster-esa-dedup-domcompmgr-io cluster-esa-dedup-domclient-io "
                    "vsan-dp-historical-stats",
    "vSAN Host": "host-domclient host-domowner host-domcompmgr host-vsansparse clom-host vsan-cpu lsom-world-cpu dom-world-cpu "
                 "vsan-memory slab-memory heap-memory system-mem cmmds-net cmmds-workload host-cpu rdt-net vsan-distribution "
                 "vsan-host-net vsan-tcpip-stats rdt-network-latency host-remotedomclient computeHost-remotedomclient "
                 "vsan-direct-host host-zdom-top-stats zdom-vtx host-pmem host-esa-dedup-store-chunksvc "
                 "host-esa-dedup-store-hashsvc host-esa-dedup-domowner-io host-esa-dedup-domcompmgr-io "
                 "host-esa-dedup-domclient-io vsan-iscsi-host",
    "Disk Group": "disk-group domcomp-sched",
    "vSAN Disk": "cache-disk capacity-disk ddh-disk clom-disk vsan-esa-disk-scsifw vsan-esa-disk-layer",
    "vSAN Network Adapter": "vsan-vnic-net vsan-pnic-net vnic-rdt-network-latency",
    "Virtual Machine": "virtual-machine remote-virtual-machine ioinsight",
    "Virtual Disk": "virtual-disk vscsi remote-virtual-disk remote-vscsi",
    "File Share": "vsan-file-service",
    "iSCSI Target": "vsan-iscsi-target",
    "iSCSI LUN": "vsan-iscsi-lun",
}
ENT2TYPE = {e: t for t, es in ENTITY.items() for e in es.split()}
PUNIT = {"number": "number", "time_ms": "ms", "rate_bytes": "bytes/s", "permille": "‰", "percentage": "%",
         "size_bytes": "bytes", "time_ns": "ns"}
TIERS = [("graphs", ""), ("advancedGraphs", "advanced"), ("verboseGraphs", "verbose"), ("hotspotGraphs", "hotspot")]

# --- query methods -> (object type, field filter). Fields under a prefix can be re-assigned with SPLIT.
M = "vim.cluster."
METHODS = [
    ("vSAN Cluster", M + "VsanSpaceReportSystem.VsanQuerySpaceUsage", None),
    ("vSAN Cluster", M + "VsanObjectSystem.QuerySyncingVsanObjectsSummary", r"^(?!objects\[\])"),
    ("vSAN Cluster", M + "VsanVcClusterConfigSystem.VsanClusterGetConfig", None),
    ("vSAN Cluster", M + "VsanVcClusterConfigSystem.VsanGetClusterRAIDInfo", None),
    ("vSAN Cluster", M + "VsanVcClusterHealthSystem.VsanHealthQueryVsanClusterHealthCheckInterval", None),
    ("vSAN Cluster", M + "VsanVcClusterHealthSystem.VsanHealthGetVsanClusterSilentChecks", None),
    ("vSAN Cluster", M + "VsanVcClusterHealthSystem.VsanHealthQueryVsanClusterHealthConfig", None),
    ("vSAN Cluster", M + "VsanCapabilitySystem.VsanGetCapabilities", None),
    ("vSAN Cluster", M + "VsanVcStretchedClusterSystem.VSANVcGetPreferredFaultDomain", None),
    ("vSAN Cluster", M + "VsanVcClusterHealthSystem.VsanQueryVcClusterHealthSummary", None),
    ("vSAN Datastore", M + "VsanSpaceReportSystem.QueryVsanManagedStorageSpaceUsage", None),
    ("vSAN Host", "vim.host.VsanSystem.QueryHostStatus", None),
    ("vSAN Host", M + "VsanVcStretchedClusterSystem.VSANVcGetWitnessHosts", None),
    ("vSAN Host", M + "VsanPerformanceManager.VsanPerfQueryNodeInformation", None),
    ("vSAN Host", M + "VsanVcClusterConfigSystem.VsanQueryClusterDrsStats", None),
    ("Disk Group", M + "VsanVcDiskManagementSystem.QueryDiskMappings", None),
    ("vSAN Disk", M + "VsanVcDiskManagementSystem.QueryVsanManagedDisks", None),
    ("vSAN Disk", "vim.host.VsanSystem.QueryDisksForVsan", None),
    ("vSAN Disk", M + "VsanVcClusterHealthSystem.VsanQueryVcClusterSmartStatsSummary", None),
    ("vSAN Object", M + "VsanObjectSystem.VsanQueryObjectIdentities", None),
    ("vSAN Object", M + "VsanObjectSystem.VosQueryVsanObjectInformation", None),
    ("vSAN Object", M + "VsanObjectSystem.VsanQueryPhysicalPlacements", None),
    ("vSAN Object", M + "VsanObjectSystem.QuerySyncingVsanObjectsSummary", r"^objects\[\]"),
    ("Virtual Machine", M + "VsanSpaceReportSystem.VsanQueryEntitySpaceUsage", None),
    ("File Share", "vim.vsan.VsanFileServiceSystem.VsanClusterQueryFileShares", None),
    ("File Share", "vim.vsan.VsanFileServiceSystem.VsanClusterQueryFsDomains", None),
    ("File Share", M + "VsanVcClusterHealthSystem.VsanClusterQueryFileServiceHealthSummary", None),
    ("iSCSI Target", M + "VsanIscsiTargetSystem.VsanVitGetIscsiTargets", None),
    ("iSCSI LUN", M + "VsanIscsiTargetSystem.VsanVitGetIscsiLUNs", None),
]
# Health summary sub-trees that belong to another object type
HEALTH_SPLIT = {"physicalDisksHealth": "vSAN Disk", "networkHealth": "vSAN Host", "hclInfo": "vSAN Host",
                "fileServiceHealth": "File Share", "objectHealth": "vSAN Object", "vmHealth": "Virtual Machine"}
NUM = {"int", "long", "short", "byte", "float", "double"}
# Numeric fields that are configuration or identifiers, not measurements -> properties
CONFIG_NUM = re.compile(r"(Id|ID|Version|Port|Vlan|VlanId|Mtu|Interval|Level|Index|Mode|Type|Generation|Value|Threshold|Timeout|Prefix|Policy|Ttl)$")


def words(s):
    s = re.sub(r"\[\]", "", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return s[:1].upper() + s[1:]


def metric_name(path):
    parts = [p for p in path.replace("[]", "").split(".") if p]
    if not parts:
        return ""
    last = parts[-1]
    name = words(re.sub(r"B$", "", last) if re.search(r"[a-z]B$", last) else last)
    if len(parts) > 1 and len(last) < 14:
        name = f"{words(parts[-2])}: {name}"
    return name


def unit(path, t):
    last = path.split(".")[-1].replace("[]", "")
    if t in ("float", "double") and re.search(r"[Rr]atio", last): return "ratio"
    if re.search(r"(B|Bytes|Size|Capacity|Space|Saving|Used|Free)$", last) and t == "long": return "bytes"
    if re.search(r"(Pct|Percent|Percentage)$", last): return "%"
    if re.search(r"ETA$", last): return "s"
    if re.search(r"^(num|total|count)|Count$|Objects|Components|ToSync$", last, re.I): return "count"
    if re.search(r"[Tt]ime(stamp)?$", last): return "time"
    return "number"


def esc(s):
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def method_short(k):
    return k.split(".")[-1]


rows_m, rows_p = {t: [] for t in TYPES}, {t: [] for t in TYPES}

# 1. performance service (live)
for e in cat["perf entity types"]:
    key = e["name"]
    t = ENT2TYPE[key]
    seen = {}
    for tier, label in TIERS:
        for g in e[tier]:
            for m in g["metrics"]:
                if m["label"] in seen:
                    continue
                seen[m["label"]] = 1
                notes = "; ".join(x for x in (label, esc(m["description"])) if x)
                rows_m[t].append(f"| {t} | {esc(m['name'])} | {PUNIT.get(g['unit'], g['unit'])} | PERF | "
                                 f"`{key}` → `{m['label']}` | {notes} |")

# 2. vCenter PerformanceManager counters (live)
for c in cat["vc perf counters (vsan groups)"]:
    key, u, summ = re.match(r"(\S+) \[(\S+)\] (.*)", c).groups()
    rows_m["Virtual Machine"].append(f"| Virtual Machine | {esc(summ)} | {u} | VCPERF | `{key}` | Entity types not checked (no vSAN cluster) |")

# 3. query methods (schema)
done = set()
for t0, mk, filt in METHODS:
    s = sch[mk]
    for path, ty in sorted(s["fields"].items()):
        if filt and not re.search(filt, path):
            continue
        t = t0
        if mk.endswith("VsanQueryVcClusterHealthSummary"):
            t = HEALTH_SPLIT.get(path.split(".")[0].replace("[]", ""), t0)
        api = f"`{method_short(mk)}` → `{path or '(value)'}`"
        if (t, api) in done:
            continue
        done.add((t, api))
        if ty in NUM and not CONFIG_NUM.search(path.split(".")[-1]):
            rows_m[t].append(f"| {t} | {(metric_name(path) or words(method_short(mk)))} | {unit(path, ty)} | VSAN | {api} | *(schema)* |")
        else:
            rows_p[t].append(f"| {t} | {(metric_name(path) or words(method_short(mk)))} | VSAN | {api} | {ty} |")

# 4. health checks (live catalog) as properties
for h in sorted(cat["health checks"], key=lambda h: (h["groupId"], h["testId"])):
    rows_p["vSAN Cluster"].append(
        f"| vSAN Cluster | Health: {esc(h['testName'])} | VSAN | `VsanQueryVcClusterHealthSummary` → "
        f"`groups[groupId={h['groupId']}].groupTests[testId={h['testId']}].testHealth` | Group: {esc(h['groupName'])} |")

LEGEND = """**Source legend**

| Code | API |
|---|---|
| PERF | vSAN performance service: `VsanPerformanceManager.VsanPerfQueryPerf` with entity `<entity type>:<id>` and the metric label. Entity types and metrics listed live by `VsanPerfGetSupportedEntityTypes` |
| VSAN | vSAN Management API query methods on vCenter (`https://<vcenter>/vsanHealth`, SOAP). Field paths from the pyVmomi 9.1 type definitions |
| VCPERF | vCenter `PerformanceManager` counters in a vSAN group (vim25 API) |
"""


def page(title, intro, header, rows):
    out = [f"# {title}", "", intro, "", LEGEND]
    out.append(header)
    out.append("|" + "---|" * (header.count("|") - 1))
    for t in TYPES:
        out += rows[t]
    return "\n".join(out) + "\n"


counts_m = {t: len(r) for t, r in rows_m.items()}
counts_p = {t: len(r) for t, r in rows_p.items()}
open(os.path.join(ROOT, "metrics-api.md"), "w", encoding="utf-8").write(page(
    "vSAN Metrics (API)",
    "Generated by `tools/build.py` from [raw/catalog.json](raw/catalog.json) and [raw/schema.json](raw/schema.json); do not edit by hand.\n\n"
    "PERF and VCPERF rows were listed live by the vSAN services of a VCF 9.1 vCenter. VSAN rows marked *(schema)* come from "
    "the API type definitions: the lab has no vSAN cluster, so their values were not seen live. Notes give the tier "
    "(advanced, verbose, hotspot; blank = default) and the description the API returns.",
    "| Object Type | Metric | Unit | Source | API field | Notes |", rows_m))
open(os.path.join(ROOT, "properties-api.md"), "w", encoding="utf-8").write(page(
    "vSAN Properties (API)",
    "Generated by `tools/build.py` from [raw/catalog.json](raw/catalog.json) and [raw/schema.json](raw/schema.json); do not edit by hand.\n\n"
    "Health checks were listed live by `VsanQueryAllSupportedHealthChecks`. All other rows come from the API type "
    "definitions (the lab has no vSAN cluster); the last column is the field's API type.",
    "| Object Type | Property | Source | API field | Type / notes |", rows_p))
print("metrics", counts_m, sum(counts_m.values()))
print("properties", counts_p, sum(counts_p.values()))
