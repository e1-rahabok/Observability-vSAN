# Generates metrics-api.md, properties-api.md and internal-api.md from raw/catalog.json (live catalogs),
# raw/schema.json (type definitions) and raw/live.json (field paths seen on a vSAN cluster).
# Re-run after tools/catalog.py, tools/schema.py or tools/live.py:  python tools/build.py
import os, re, json

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
cat = json.load(open(os.path.join(ROOT, "raw", "catalog.json")))
sch = json.load(open(os.path.join(ROOT, "raw", "schema.json")))
_lp = os.path.join(ROOT, "raw", "live.json")
live = json.load(open(_lp)) if os.path.exists(_lp) else {"methods": {}, "perf": {}, "vim25": {}, "vcperf": {}, "environment": {}}
LIVE = {k: {re.sub(r" <MoRef>$", "", p) for p in v.get("fields", [])} for k, v in live["methods"].items()}
LPERF = live["perf"]
ENV = live["environment"]

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
    # added after the first live run: supported query methods that returned populated fields
    ("vSAN Cluster", M + "VsanVcDiskManagementSystem.QueryClusterDataEfficiencyCapacityState", None),
    ("vSAN Cluster", M + "VsanPerformanceManager.VsanPerfQueryStatsObjectInformation", None),
    ("vSAN Cluster", M + "VsanPerformanceManager.VsanPerfQueryClusterHealth", None),
    ("vSAN Host", M + "VsanVcDiskManagementSystem.RetrieveAllFlashCapabilities", None),
    ("vSAN Host", M + "VsanVcClusterHealthSystem.VsanVcClusterGetHclInfo", None),
    ("vSAN Object", M + "VsanVcClusterHealthSystem.VsanQueryVcClusterObjExtAttrs", None),
]
# vim25 properties of vSAN interest (raw/live.json "vim25"; no schema walk, so no types)
VIM = [("vSAN Cluster", "ClusterComputeResource.configurationEx.vsanConfigInfo"),
       ("vSAN Host", "ClusterComputeResource.configurationEx.vsanHostConfig"),
       ("vSAN Host", "HostSystem.config.vsanHostConfig"),
       ("vSAN Host", "HostSystem.runtime.vsanRuntimeInfo"),
       ("vSAN Datastore", "Datastore.summary (vsan)"),
       ("vSAN Datastore", "Datastore.info (vsan)"),
       ("vSAN Datastore", "Datastore.capability (vsan)")]
VIM_METRIC = re.compile(r"^(capacity|freeSpace|uncommitted)$")
# Host-side internal API (vim.host.VsanInternalSystem, returns JSON strings) -> internal-api.md
INTERNAL = [("vSAN Host", "QueryVsanStatistics"), ("vSAN Host", "QueryCmmds"), ("vSAN Disk", "QueryPhysicalVsanDisks"),
            ("vSAN Object", "QueryVsanObjects"), ("vSAN Object", "GetVsanObjExtAttrs")]
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


rows_m, rows_p, rows_i = {t: [] for t in TYPES}, {t: [] for t in TYPES}, {t: [] for t in TYPES}
OK = "✓"


def perf_live(key, label):
    """Live column for a PERF row: ✓ when the metric returned values on the cluster."""
    if key not in LPERF:
        return ""
    return OK if label in LPERF[key]["withData"] else "no data"


# 1. performance service (live catalog, plus metrics returned live that the catalog does not list)
seen = set()  # (entity type, label); some entity types (disk-group) appear twice in the catalog
for e in cat["perf entity types"]:
    key = e["name"]
    t = ENT2TYPE[key]
    for tier, label in TIERS:
        for g in e[tier]:
            for m in g["metrics"]:
                if (key, m["label"]) in seen:
                    continue
                seen.add((key, m["label"]))
                notes = "; ".join(x for x in (label, esc(m["description"])) if x)
                rows_m[t].append(f"| {t} | {esc(m['name'])} | {PUNIT.get(g['unit'], g['unit'])} | PERF | "
                                 f"`{key}` → `{m['label']}` | {perf_live(key, m['label'])} | {notes} |")
for key, v in LPERF.items():
    t = ENT2TYPE[key]
    for l in v.get("unlisted", []):
        if (key, l) not in seen:
            seen.add((key, l))
            rows_m[t].append(f"| {t} | {words(l)} | | PERF | `{key}` → `{l}` | {OK} | "
                             f"*(live only)* returned by `VsanPerfQueryPerf`, not listed by `VsanPerfGetSupportedEntityTypes` |")

# 2. vCenter PerformanceManager counters (live catalog)
vc_avail = {c for v in live["vcperf"].values() for c in v}
for c in cat["vc perf counters (vsan groups)"]:
    key, u, summ = re.match(r"(\S+) \[(\S+)\] (.*)", c).groups()
    if live["vcperf"]:
        lv, note = (OK, "") if key in vc_avail else ("not available", "Defined, but `QueryAvailablePerfMetric` offers it on no vSAN cluster, host, datastore or VM")
    else:
        lv, note = "", "Entity types not checked (no vSAN cluster)"
    rows_m["Virtual Machine"].append(f"| Virtual Machine | {esc(summ)} | {u} | VCPERF | `{key}` | {lv} | {note} |")

# 3. query methods (schema, marked with what the live cluster returned)
done = set()
for t0, mk, filt in METHODS:
    s = sch[mk]
    seen_live = LIVE.get(mk, set())
    fields = dict(s["fields"])
    for p in seen_live - set(fields):            # returned live but absent from the pyVmomi type definitions
        fields[p] = None
    for path, ty in sorted(fields.items()):
        if filt and not re.search(filt, path):
            continue
        t = t0
        if mk.endswith("VsanQueryVcClusterHealthSummary"):
            t = HEALTH_SPLIT.get(path.split(".")[0].replace("[]", ""), t0)
        api = f"`{method_short(mk)}` → `{path or '(value)'}`"
        if (t, api) in done:
            continue
        done.add((t, api))
        lv = OK if path in seen_live else ""
        name = metric_name(path) or words(method_short(mk))
        if ty is None:
            rows_p[t].append(f"| {t} | {name} | VSAN | {api} | {lv} | *(live only)* not in the pyVmomi 9.1 type definitions |")
        elif ty in NUM and not CONFIG_NUM.search(path.split(".")[-1]):
            rows_m[t].append(f"| {t} | {name} | {unit(path, ty)} | VSAN | {api} | {lv} | {'' if lv else '*(schema)*'} |")
        else:
            rows_p[t].append(f"| {t} | {name} | VSAN | {api} | {lv} | {ty}{'' if lv else ' *(schema)*'} |")

# 4. health checks (live catalog) as properties; ✓ when the cluster's health summary contained the test
live_hc = set(live.get("health", []))
for h in sorted(cat["health checks"], key=lambda h: (h["groupId"], h["testId"])):
    lv = (OK if f"{h['groupId']}/{h['testId']}" in live_hc else "not run") if live_hc else ""
    rows_p["vSAN Cluster"].append(
        f"| vSAN Cluster | Health: {esc(h['testName'])} | VSAN | `VsanQueryVcClusterHealthSummary` → "
        f"`groups[groupId={h['groupId']}].groupTests[testId={h['testId']}].testHealth` | {lv} | Group: {esc(h['groupName'])} |")

# 5. vim25 properties on cluster, host and datastore objects (live)
for t, key in VIM:
    obj = key.split(" ")[0]
    for path in live["vim25"].get(key, []):
        if path.startswith("_error"):
            continue
        path = re.sub(r" <MoRef>$", "", path)
        api = f"`{obj}` → `{path}`"
        if VIM_METRIC.search(path.split(".")[-1]):
            rows_m[t].append(f"| {t} | {metric_name(path)} | bytes | VIM | {api} | {OK} | |")
        else:
            rows_p[t].append(f"| {t} | {metric_name(path)} | VIM | {api} | {OK} | |")

# 6. host-side internal API (JSON strings; field names only) -> internal-api.md
for t, m in INTERNAL:
    k = "vim.host.VsanInternalSystem." + m
    for path in sorted(LIVE.get(k, set())):
        rows_i[t].append(f"| {t} | VSANINT | `{m}` → `{path}` |")

LEGEND = """**Source legend**

| Code | API |
|---|---|
| PERF | vSAN performance service: `VsanPerformanceManager.VsanPerfQueryPerf` with entity `<entity type>:<id>` and the metric label. Entity types and metrics listed live by `VsanPerfGetSupportedEntityTypes` |
| VSAN | vSAN Management API query methods on vCenter (`https://<vcenter>/vsanHealth`, SOAP). Field paths from the pyVmomi 9.1 type definitions |
| VCPERF | vCenter `PerformanceManager` counters in a vSAN group (vim25 API) |
| VIM | vSAN properties of vCenter inventory objects (vim25 API): `ClusterComputeResource`, `HostSystem`, `Datastore` |

**Live column**: ✓ = returned with a value on a live vSAN cluster; *no data* = the entity type answered but this metric
had no values; *not run* = health check absent from the cluster's health summary; blank = not seen live (see *(schema)*).
"""


def env_line():
    if not ENV:
        return "No live vSAN cluster has been collected yet."
    feats = [k for k in ("dedup", "encryption", "fileService", "iscsi", "stretchedOr2Node", "perfVerboseMode") if not ENV.get(k)]
    return (f"Live evidence from `tools/live.py` ({live['collected']}): vCenter and ESX {ENV['vcenter']}, one "
            f"{'ESA' if ENV.get('esa') else 'OSA'} vSAN cluster with {ENV['hosts']} hosts. Not enabled on that cluster, so "
            f"their fields could not be seen: {', '.join(feats)}.")


def page(title, intro, header, rows, extra=""):
    out = [f"# {title}", "", intro, "", env_line(), "", LEGEND]
    out.append(header)
    out.append("|" + "---|" * (header.count("|") - 1))
    for t in TYPES:
        out += rows[t]
    return "\n".join(out) + "\n" + extra


def coverage():
    if not LPERF:
        return ""
    out = ["", "## Live coverage by performance entity type", "",
           "How each entity type answered `VsanPerfQueryPerf` on the live cluster. *ID format* is the entity ID that "
           "returned values (`*` = wildcard accepted). Entity types with no data belong to features that are not "
           "enabled on that cluster (ESA, deduplication, file service, iSCSI, vSAN Direct, PMem, remote datastores, "
           "data protection), or need verbose mode.", "",
           "| Entity type | Object type | ID format | Entities | Listed metrics | With data | Live only |", "|---|---|---|---|---|---|---|"]
    for k, v in sorted(LPERF.items(), key=lambda x: (TYPES.index(ENT2TYPE[x[0]]), x[0])):
        out.append(f"| `{k}` | {ENT2TYPE[k]} | {', '.join(f'`{f}`' for f in v['idFormats'])} | {v['entities'] or ''} | "
                   f"{v['listed']} | {len(v['withData'])} | {len(v.get('unlisted', [])) or ''} |")
    return "\n".join(out) + "\n"


SRC = "[raw/catalog.json](raw/catalog.json), [raw/schema.json](raw/schema.json) and [raw/live.json](raw/live.json)"
counts_m = {t: len(r) for t, r in rows_m.items()}
counts_p = {t: len(r) for t, r in rows_p.items()}
counts_i = {t: len(r) for t, r in rows_i.items()}
open(os.path.join(ROOT, "metrics-api.md"), "w", encoding="utf-8").write(page(
    "vSAN Metrics (API)",
    f"Generated by `tools/build.py` from {SRC}; do not edit by hand.\n\n"
    "PERF and VCPERF rows were listed live by the vSAN services of a VCF 9.1 vCenter; PERF rows marked *(live only)* "
    "returned values but are missing from that list. VSAN rows come from the API type definitions; those marked "
    "*(schema)* were not seen with a value on the live cluster. Notes give the tier (advanced, verbose, hotspot; blank "
    "= default) and the description the API returns. Raw host-internal counters are in [internal-api.md](internal-api.md).",
    "| Object Type | Metric | Unit | Source | API field | Live | Notes |", rows_m, coverage()))
open(os.path.join(ROOT, "properties-api.md"), "w", encoding="utf-8").write(page(
    "vSAN Properties (API)",
    f"Generated by `tools/build.py` from {SRC}; do not edit by hand.\n\n"
    "Health checks were listed live by `VsanQueryAllSupportedHealthChecks`. VSAN rows come from the API type "
    "definitions; the last column is the field's API type, marked *(schema)* when the field was not seen with a value "
    "on the live cluster.",
    "| Object Type | Property | Source | API field | Live | Type / notes |", rows_p))
open(os.path.join(ROOT, "internal-api.md"), "w", encoding="utf-8").write(
    "# vSAN Host Internal API (field paths)\n\n"
    f"Generated by `tools/build.py` from [raw/live.json](raw/live.json); do not edit by hand.\n\n"
    "`vim.host.VsanInternalSystem` on each ESX host (vim25, `HostSystem.configManager.vsanInternalSystem`) returns JSON "
    "strings rather than typed objects; this is an internal interface that Broadcom does not document. These are the "
    "JSON field paths seen on the live cluster. Instance-specific keys are normalized: `*` = UUID or device name, "
    "`#` = number (world ID, index, instance), `<controller>:<unit>` = virtual disk position. `QueryVsanStatistics` "
    "holds raw cumulative counters (bytes, counts, latency sums) from which the performance service derives its metrics.\n\n"
    + env_line() + "\n\n| Object Type | Source | API field |\n|---|---|---|\n"
    + "\n".join(r for t in TYPES for r in rows_i[t]) + "\n")
print("metrics", counts_m, sum(counts_m.values()))
print("properties", counts_p, sum(counts_p.values()))
print("internal", {k: v for k, v in counts_i.items() if v}, sum(counts_i.values()))
