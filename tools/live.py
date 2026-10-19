# Collects live evidence from a vCenter with a vSAN cluster and writes raw/live.json:
#   - environment shape (counts and feature flags only)
#   - performance service: per entity type, how many entities answered and which metric labels returned data
#   - every read-only vSAN query method in raw/schema.json that can be called safely: the leaf field paths
#     that came back populated
#   - vim25 vSAN properties on cluster, host and datastore objects: populated field paths
#   - vCenter PerformanceManager vSAN counters available per managed object type
#   - health checks present in the cluster health summary
# Values, names, UUIDs and addresses are discarded. Methods that start tests, generate load or change
# anything are not called. Run:  . tools/env.ps1 live ; python tools/live.py
import sys, os, re, json, datetime, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
UUID = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$|^[0-9a-f]{8}-[0-9a-f]{16}$|"
                  r"^(naa|t10|eui|mpx|vml)\.|^vmhba|^vmk\d|^vmnic\d|^\d+\.\d+\.\d+\.\d+$|^[0-9a-f]{16,}$", re.I)
SECRET = []  # names and addresses scrubbed from error messages


def scrub(s):
    for x in SECRET:
        if x:
            s = s.replace(x, "<name>")
    s = re.sub(r"\d+\.\d+\.\d+\.\d+", "<ip>", s)
    s = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", s, flags=re.I)
    return s[:200]


def norm(o):
    """JSON values from the internal APIs: replace instance-specific keys (UUIDs, device names) with *."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            k = "*" if UUID.search(str(k)) else k
            k = re.sub(r"^\d+$", "#", k)                                     # world ids, indexes
            k = re.sub(r"(?<=[A-Za-z][-_])\d+(?=$|-taken$)", "#", k)          # stats-0, stats-1, ... (keys can be dotted)
            k = re.sub(r"[-_]0x[0-9a-f]+$", "", k)                           # slab names carry memory addresses
            k = re.sub(r"_DG_\d+", "_DG_#", k)                               # per disk group slabs
            k = re.sub(r"^(scsi|nvme|sata|ide)\d+:\d+$", "<controller>:<unit>", k)
            out[k] = norm(v) if k not in out else out[k]
        return out
    if isinstance(o, list):
        return [norm(v) for v in o]
    return o


def fpaths(o):
    if isinstance(o, str) and o[:1] in "{[":
        try:
            o = norm(json.loads(o))
        except ValueError:
            pass
    return sorted(paths(o))


R = {"collected": datetime.date.today().isoformat(), "methods": {}, "perf": {}, "vim25": {}, "vcperf": {}}


def call(key, fn):
    try:
        res = fn()
        prev = R["methods"].get(key, {}).get("fields", [])
        R["methods"][key] = {"fields": sorted(set(prev) | set(fpaths(res))), "empty": res in (None, [], "")}
        return res
    except Exception as e:
        if "fields" not in R["methods"].get(key, {}):
            R["methods"][key] = {"error": f"{type(e).__name__}: {scrub(getattr(e, 'msg', '') or str(e))}"}
        return None


cl = vsan_clusters()
assert cl, "no vSAN cluster"
C = cl[0]
H = list(C.host)
DS = [d for d in objects(vim.Datastore) if d.summary.type == "vsan"]
VMS = [v for d in DS for v in d.vm]
SECRET += [C.name] + [h.name for h in H] + [d.name for d in DS] + [v.name for v in VMS] + [VC_HOST]

# --- vSAN managed objects on vCenter
CS, HS, SR = vsan["vsan-cluster-config-system"], vsan["vsan-cluster-health-system"], vsan["vsan-cluster-space-report-system"]
OS_, PM, DM = vsan["vsan-cluster-object-system"], vsan["vsan-performance-manager"], vsan["vsan-disk-management-system"]
ST, IS, FS = vsan["vsan-stretched-cluster-system"], vsan["vsan-cluster-iscsi-target-system"], vsan["vsan-cluster-file-service-system"]
CAP = vsan["vsan-vc-capability-system"]
P = "vim.cluster."

cfg = call(P + "VsanVcClusterConfigSystem.VsanClusterGetConfig", lambda: CS.VsanClusterGetConfig(cluster=C))
call(P + "VsanVcClusterConfigSystem.VsanGetClusterRAIDInfo", lambda: CS.VsanGetClusterRAIDInfo(cluster=C))
call(P + "VsanVcClusterConfigSystem.VsanGetConfigurationLimits", lambda: CS.VsanGetConfigurationLimits())
call(P + "VsanVcClusterConfigSystem.VsanQueryClusterDrsStats", lambda: CS.VsanQueryClusterDrsStats(cluster=C))

call(P + "VsanSpaceReportSystem.VsanQuerySpaceUsage", lambda: SR.VsanQuerySpaceUsage(cluster=C))
call(P + "VsanSpaceReportSystem.QueryVsanManagedStorageSpaceUsage",
     lambda: SR.QueryVsanManagedStorageSpaceUsage(cluster=C, querySpec=vim.cluster.QueryVsanManagedStorageSpaceUsageSpec(
         datastoreTypes=["vsan"])))
for et in ("virtualMachine", "vm", "cluster", "host"):
    call(P + "VsanSpaceReportSystem.VsanQueryEntitySpaceUsage",
         lambda: SR.VsanQueryEntitySpaceUsage(cluster=C, querySpec=vim.cluster.VsanSpaceQuerySpec(entityType=et)))

ids = call(P + "VsanObjectSystem.VsanQueryObjectIdentities",
           lambda: OS_.VsanQueryObjectIdentities(cluster=C, includeHealth=True, includeObjIdentity=True, includeSpaceSummary=True))
uuids = sorted({i.uuid for i in (getattr(ids, "identities", None) or []) if getattr(i, "uuid", None)})[:50]
call(P + "VsanObjectSystem.VosQueryVsanObjectInformation",
     lambda: OS_.VosQueryVsanObjectInformation(cluster=C, vsanObjectQuerySpecs=[vim.cluster.VsanObjectQuerySpec(uuid=u) for u in uuids[:20]]))
call(P + "VsanObjectSystem.VsanQueryPhysicalPlacements",
     lambda: OS_.VsanQueryPhysicalPlacements(cluster=C, specs=vim.cluster.VsanQueryPhysicalPlacementSpecs(vms=VMS[:5])))
call(P + "VsanObjectSystem.QuerySyncingVsanObjectsSummary",
     lambda: OS_.QuerySyncingVsanObjectsSummary(cluster=C, syncingObjectFilter=vim.cluster.VsanSyncingObjectFilter(numberOfObjects=100)))
call(P + "VsanObjectSystem.VsanQueryInaccessibleVmSwapObjects", lambda: OS_.VsanQueryInaccessibleVmSwapObjects(cluster=C))

call(P + "VsanPerformanceManager.VsanPerfQueryNodeInformation", lambda: PM.VsanPerfQueryNodeInformation(cluster=C))
call(P + "VsanPerformanceManager.VsanPerfQueryStatsObjectInformation", lambda: PM.VsanPerfQueryStatsObjectInformation(cluster=C))
call(P + "VsanPerformanceManager.VsanPerfQueryClusterHealth", lambda: PM.VsanPerfQueryClusterHealth(cluster=C))
call(P + "VsanPerformanceManager.VsanPerfGetSupportedHotspotEntityTypes", lambda: PM.VsanPerfGetSupportedHotspotEntityTypes(cluster=C))
call(P + "VsanPerformanceManager.VsanPerfGetAggregatedEntityTypes", lambda: PM.VsanPerfGetAggregatedEntityTypes())
call(P + "VsanPerformanceManager.VsanPerfGetSupportedDiagnosticExceptions", lambda: PM.VsanPerfGetSupportedDiagnosticExceptions())
call(P + "VsanPerformanceManager.VsanPerfQueryTimeRanges",
     lambda: PM.VsanPerfQueryTimeRanges(cluster=C, querySpec=vim.cluster.VsanPerfTimeRangeQuerySpec()))
now = si.CurrentTime()
call(P + "VsanPerformanceManager.QueryVsanPerfTopEntities", lambda: PM.QueryVsanPerfTopEntities(cluster=C,
     querySpec=vim.cluster.VsanPerfTopQuerySpec(entity="virtual-machine", metricId="iopsRead",
                                                timeStamp=now - datetime.timedelta(minutes=10), numEntities=5)))
hot = PM.VsanPerfGetSupportedHotspotEntityTypes(cluster=C) or []
for ht in hot:
    for sm in (ht.sortingMetrics or [])[:1]:
        call(P + "VsanPerformanceManager.QueryVsanPerfHotspotEntities", lambda: PM.QueryVsanPerfHotspotEntities(cluster=C,
             querySpec=vim.cluster.VsanPerfHotspotQuerySpec(entity=ht.name, metricId=sm.label, numEntities=5,
                                                            startTime=now - datetime.timedelta(hours=1), endTime=now)))

HP = P + "VsanVcClusterHealthSystem."
hs = call(HP + "VsanQueryVcClusterHealthSummary",
          lambda: HS.VsanQueryVcClusterHealthSummary(cluster=C, includeObjUuids=True, fetchFromCache=True, perspective="defaultView"))
call(HP + "VsanClusterQueryFileServiceHealthSummary",
     lambda: HS.VsanClusterQueryFileServiceHealthSummary(cluster=C, includeFileServerHealth=True, includeFileShareHealth=True))
call(HP + "VsanHealthGetVsanClusterSilentChecks", lambda: HS.VsanHealthGetVsanClusterSilentChecks(cluster=C))
call(HP + "VsanHealthQueryVsanClusterHealthCheckInterval", lambda: HS.VsanHealthQueryVsanClusterHealthCheckInterval(cluster=C))
call(HP + "VsanHealthQueryVsanClusterHealthConfig", lambda: HS.VsanHealthQueryVsanClusterHealthConfig(cluster=C))
call(HP + "VsanHealthQueryVsanProxyConfig", lambda: HS.VsanHealthQueryVsanProxyConfig())
call(HP + "VsanQueryAllSupportedHealthChecks", lambda: HS.VsanQueryAllSupportedHealthChecks())
call(HP + "VsanQueryClusterHistoricalHealth", lambda: HS.VsanQueryClusterHistoricalHealth(
    spec=vim.cluster.VsanHistoricalHealthQuerySpec(clusters=[C], start=now - datetime.timedelta(days=1), end=now)))
call(HP + "VsanQueryVcClusterNetworkPerfHistoryTest", lambda: HS.VsanQueryVcClusterNetworkPerfHistoryTest(cluster=C, count=1))
call(HP + "VsanQueryVcClusterObjExtAttrs", lambda: HS.VsanQueryVcClusterObjExtAttrs(cluster=C, uuids=uuids[:20]))
call(HP + "VsanQueryVcClusterSmartStatsSummary", lambda: HS.VsanQueryVcClusterSmartStatsSummary(cluster=C))
call(HP + "VsanQueryVcClusterVmdkLoadHistoryTest", lambda: HS.VsanQueryVcClusterVmdkLoadHistoryTest(cluster=C, count=1))
call(HP + "VsanQueryVcClusterVmdkWorkloadTypes", lambda: HS.VsanQueryVcClusterVmdkWorkloadTypes())
call(HP + "VsanVcClusterGetHclInfo", lambda: HS.VsanVcClusterGetHclInfo(cluster=C, includeHostsResult=True, includeVendorInfo=True))
call(HP + "VsanVcClusterQueryVerifyHealthSystemVersions", lambda: HS.VsanVcClusterQueryVerifyHealthSystemVersions(cluster=C))
call(HP + "VsanGetHclConstraints", lambda: HS.VsanGetHclConstraints(cluster=C, release=H[0].config.product.version))

DP = P + "VsanVcDiskManagementSystem."
call(DP + "QueryClusterDataEfficiencyCapacityState", lambda: DM.QueryClusterDataEfficiencyCapacityState(cluster=C))
call(DP + "RetrieveAllFlashCapabilities", lambda: DM.RetrieveAllFlashCapabilities(cluster=C))
for h in H:
    call(DP + "QueryDiskMappings", lambda: DM.QueryDiskMappings(host=h))
    call(DP + "QueryVsanManagedDisks", lambda: DM.QueryVsanManagedDisks(host=h))

SP = P + "VsanVcStretchedClusterSystem."
call(SP + "VSANVcGetPreferredFaultDomain", lambda: ST.VSANVcGetPreferredFaultDomain(cluster=C))
call(SP + "VSANVcGetWitnessHosts", lambda: ST.VSANVcGetWitnessHosts(cluster=C))
call(SP + "VSANIsWitnessVirtualAppliance", lambda: ST.VSANIsWitnessVirtualAppliance(hosts=H))
call(SP + "VSANVcIsWitnessHost", lambda: ST.VSANVcIsWitnessHost(host=H[0]))
call(SP + "VSANVcRetrieveStretchedClusterVcCapability",
     lambda: ST.VSANVcRetrieveStretchedClusterVcCapability(cluster=C, verifyAllConnected=False))

IP = P + "VsanIscsiTargetSystem."
call(IP + "VsanVitGetIscsiTargets", lambda: IS.VsanVitGetIscsiTargets(cluster=C))
call(IP + "VsanVitGetIscsiLUNs", lambda: IS.VsanVitGetIscsiLUNs(cluster=C))
call(IP + "VsanVitGetHomeObject", lambda: IS.VsanVitGetHomeObject(cluster=C))
call(IP + "VsanVitQueryIscsiTargetServiceVersion", lambda: IS.VsanVitQueryIscsiTargetServiceVersion())

FP = "vim.vsan.VsanFileServiceSystem."
call(FP + "VsanClusterQueryFileShares", lambda: FS.VsanClusterQueryFileShares(querySpec=vim.vsan.FileShareQuerySpec(), cluster=C))
call(FP + "VsanClusterQueryFsDomains", lambda: FS.VsanClusterQueryFsDomains(querySpec=vim.vsan.FileServiceDomainQuerySpec(), cluster=C))
call(FP + "VsanClusterQueryShareSnapshots",
     lambda: FS.VsanClusterQueryShareSnapshots(querySpec=vim.vsan.FileShareSnapshotQuerySpec(), cluster=C))
call(FP + "VsanQueryFileServiceOvfs", lambda: FS.VsanQueryFileServiceOvfs())

call(P + "VsanCapabilitySystem.VsanGetCapabilities", lambda: CAP.VsanGetCapabilities(targets=[C] + H))

# --- host-side vSAN systems (vim25)
for h in H:
    vs, vi = h.configManager.vsanSystem, h.configManager.vsanInternalSystem
    call("vim.host.VsanSystem.QueryHostStatus", lambda: vs.QueryHostStatus())
    call("vim.host.VsanSystem.QueryDisksForVsan", lambda: vs.QueryDisksForVsan())
    call("vim.host.VsanInternalSystem.QueryPhysicalVsanDisks", lambda: vi.QueryPhysicalVsanDisks(props=None))
    call("vim.host.VsanInternalSystem.QueryVsanObjects", lambda: vi.QueryVsanObjects(uuids=uuids[:10]))
    call("vim.host.VsanInternalSystem.QuerySyncingVsanObjects", lambda: vi.QuerySyncingVsanObjects(uuids=[]))
    call("vim.host.VsanInternalSystem.QueryVsanObjectUuidsByFilter", lambda: vi.QueryVsanObjectUuidsByFilter(limit=10))
    call("vim.host.VsanInternalSystem.GetVsanObjExtAttrs", lambda: vi.GetVsanObjExtAttrs(uuids=uuids[:10]))
    call("vim.host.VsanInternalSystem.QueryVsanStatistics", lambda: vi.QueryVsanStatistics(labels=[
        "dom", "dom-objects", "lsom", "worldlets", "plog", "mem", "cpus", "slabs", "vscsi", "cbrc", "disks", "rdtassocsets",
        "system-mem", "pnics", "rdtglobal", "lsom-node", "dom-objects-counts"]))
    call("vim.host.VsanInternalSystem.QueryCmmds", lambda: vi.QueryCmmds(queries=[
        vim.host.VsanInternalSystem.CmmdsQuery(type=t) for t in
        ("HOSTNAME", "NODE", "DISK", "DISK_STATUS", "DISK_USAGE", "DOM_OBJECT", "LSOM_OBJECT", "POLICY", "CONFIG_STATUS",
         "HEALTH_STATUS", "NET_INTERFACE", "HOST_VSAN_UNICAST_LIST", "SUBCLUSTER", "MASTER_SIGNATURE")]))

# --- vim25 properties of vSAN interest
V = R["vim25"]
def vprop(key, o):
    try:
        V[key] = sorted(set(V.get(key, [])) | set(fpaths(o)))
    except Exception as e:
        V.setdefault(key, [f"_error {type(e).__name__}"])
vprop("ClusterComputeResource.configurationEx.vsanConfigInfo", C.configurationEx.vsanConfigInfo)
vprop("ClusterComputeResource.configurationEx.vsanHostConfig", C.configurationEx.vsanHostConfig)
vprop("ClusterComputeResource.summary (vSAN cluster)", C.summary)
for h in H:
    vprop("HostSystem.config.vsanHostConfig", h.config.vsanHostConfig)
    vprop("HostSystem.runtime.vsanRuntimeInfo", h.runtime.vsanRuntimeInfo)
for d in DS:
    vprop("Datastore.summary (vsan)", d.summary)
    vprop("Datastore.info (vsan)", d.info)
    vprop("Datastore.capability (vsan)", d.capability)

# --- performance service: per entity type, which entity ID formats answer and which metric labels returned data.
# Wildcards (type:*) work only for some types; the others need real IDs. Formats are tried in order and recorded
# by shape (e.g. "<nodeUuid>|*"); the IDs themselves are discarded.
cu = C.configurationEx.vsanConfigInfo.defaultConfig.uuid
nodes = [h.config.vsanHostConfig.clusterInfo.nodeUuid for h in H]
maps = [m for h in H for m in (DM.QueryDiskMappings(host=h) or [])]
dgs = [m.mapping.ssd.vsanDiskInfo.vsanUuid for m in maps if m.mapping and m.mapping.ssd]
cds = [d.vsanDiskInfo.vsanUuid for m in maps if m.mapping for d in (m.mapping.nonSsd or [])]
vmks = [f"{h.config.vsanHostConfig.clusterInfo.nodeUuid}|{p.device}" for h in H for p in (h.config.vsanHostConfig.networkInfo.port or [])]
vmus = [v.config.instanceUuid for v in VMS if v.runtime.powerState == "poweredOn"][:10]
FORMATS = [("*", ["*"]), ("<clusterUuid>", [cu]), ("<nodeUuid>", nodes), ("<diskGroupUuid>", dgs), ("<diskUuid>", cds[:12]),
           ("<nodeUuid>|*", [f"{n}|*" for n in nodes]), ("<nodeUuid>|<vmknic>", vmks), ("<vmInstanceUuid>", vmus),
           ("<vmInstanceUuid>|*", [f"{u}|*" for u in vmus])]
ents = PM.VsanPerfGetSupportedEntityTypes(cluster=C)
start, end = now - datetime.timedelta(hours=2), now


def perf_query(etype, idlist, errs):
    """VsanPerfQueryPerf for all IDs at once; if the batch fails (one bad ID fails it all), retry each ID alone."""
    spec = lambda i: vim.cluster.VsanPerfQuerySpec(entityRefId=f"{etype}:{i}", startTime=start, endTime=end)
    try:
        return PM.VsanPerfQueryPerf(querySpecs=[spec(i) for i in idlist], cluster=C) or []
    except Exception as ex:
        errs.add(type(ex).__name__)
    out = []
    for i in idlist if len(idlist) > 1 else []:
        try:
            out += PM.VsanPerfQueryPerf(querySpecs=[spec(i)], cluster=C) or []
        except Exception as ex:
            errs.add(type(ex).__name__)
    return out
for e in ents:
    labels = {m.label for tier in ("graphs", "advancedGraphs", "verboseGraphs", "hotspotGraphs")
              for g in (getattr(e, tier, None) or []) for m in (g.metrics or [])}
    rec = {"listed": len(labels), "idFormats": [], "entities": 0, "withData": [], "noData": [], "unlisted": []}
    seen, errs = set(), set()
    for shape, idlist in FORMATS:
        if not idlist:
            continue
        res = perf_query(e.name, idlist, errs)
        if not res:
            continue
        got, n = set(), set()
        for r in res or []:
            for v in r.value or []:
                if v.values and any(x not in ("", "None") for x in v.values.split(",")):
                    got.add(v.metricId.label)
                    n.add(r.entityRefId)
        if got:
            rec["idFormats"].append(shape)
            rec["entities"] = max(rec["entities"], len(n))
            seen |= got
    rec["withData"] = sorted(seen)
    rec["noData"] = sorted(labels - seen)
    rec["unlisted"] = sorted(seen - labels)
    if not seen and errs:
        rec["errors"] = sorted(errs)
    R["perf"][e.name] = rec

# --- vCenter PerformanceManager: vSAN counters available per managed object type
pm = content.perfManager
ctr = {c.key: f"{c.groupInfo.key}.{c.nameInfo.key}.{c.rollupType}" for c in pm.perfCounter}
targets = {"ClusterComputeResource": [C], "HostSystem": H, "Datastore": DS, "VirtualMachine": VMS[:10]}
for kind, objs in targets.items():
    found = set()
    for o in objs:
        for interval in (None, 300):
            try:
                ms = pm.QueryAvailablePerfMetric(entity=o, intervalId=interval) if interval else \
                     pm.QueryAvailablePerfMetric(entity=o, intervalId=pm.QueryPerfProviderSummary(entity=o).refreshRate)
            except Exception:
                continue
            found |= {ctr[m.counterId] for m in ms or [] if m.counterId in ctr and "vsan" in ctr[m.counterId].split(".")[0].lower()}
    R["vcperf"][kind] = sorted(found)

# --- health: group and test ids present in the live summary
R["health"] = sorted({f"{g.groupId}/{t.testId}" for g in (getattr(hs, "groups", None) or [])
                      for t in (g.groupTests or [])}) if hs else []

# --- environment shape
dg = R["methods"].get(DP + "QueryDiskMappings", {}).get("fields", [])
R["environment"] = {
    "vcenter": content.about.version, "build": content.about.build, "esx": H[0].config.product.version,
    "vsanClusters": len(cl), "hosts": len(H), "vsanDatastores": len(DS), "vmsOnVsan": len(VMS),
    "objects": len((getattr(ids, "identities", None) or [])),
    "esa": bool(getattr(cfg, "vsanEsaEnabled", False)) if cfg else None,
    "diskGroups (OSA)": bool(dg),
    "dedup": bool(getattr(getattr(cfg, "dataEfficiencyConfig", None), "dedupEnabled", False)),
    "encryption": bool(getattr(getattr(cfg, "dataEncryptionConfig", None), "encryptionEnabled", False)),
    "fileService": bool(getattr(getattr(cfg, "fileServiceConfig", None), "enabled", False)),
    "iscsi": bool(getattr(getattr(cfg, "iscsiConfig", None), "enabled", False)),
    "perfService": bool(getattr(getattr(cfg, "perfsvcConfig", None), "enabled", False)),
    "perfVerboseMode": bool(getattr(getattr(cfg, "perfsvcConfig", None), "verboseMode", False)),
    "perfDiagnosticMode": bool(getattr(getattr(cfg, "perfsvcConfig", None), "diagnosticMode", False)),
    "stretchedOr2Node": bool(R["methods"].get(SP + "VSANVcGetWitnessHosts", {}).get("fields")),
}

out = os.path.join(ROOT, "raw", "live.json")
txt = json.dumps(R, indent=1, sort_keys=True)
# Guard: no instance name may appear in the output, unless the name is an ordinary API word
# (a VM called "vcenter" or a datastore called "vsan" matches field names, not data).
vocab = (open(os.path.join(ROOT, "raw", "schema.json")).read() + open(os.path.join(ROOT, "raw", "catalog.json")).read()
         + " ".join(R["environment"])).lower()
leak = [x for x in SECRET if x and x in txt and x.lower() not in vocab]
if leak:
    for i, ln in enumerate(txt.splitlines()):
        if any(x in ln for x in leak):
            print("LEAK line", i, scrub(ln.strip()))
    sys.exit(f"refusing to write: {len(leak)} instance names found in output")
open(out, "w").write(txt)
print(json.dumps(R["environment"], indent=1))
ok = {k: len(v["fields"]) for k, v in R["methods"].items() if "fields" in v}
print("methods called", len(R["methods"]), "with fields", sum(1 for v in ok.values() if v), "fields", sum(ok.values()))
for k, v in sorted(R["methods"].items()):
    print(f"  {k.split('.')[-1]:50} {len(v['fields']) if 'fields' in v else v['error']}")
print("perf entity types", len(R["perf"]), "with data", sum(1 for v in R["perf"].values() if v["withData"]),
      "labels with data", sum(len(v["withData"]) for v in R["perf"].values()))
print("vcperf", {k: len(v) for k, v in R["vcperf"].items()}, "health tests", len(R["health"]))
