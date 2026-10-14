# Walks the pyVmomi type definitions (no lab needed) and writes raw/schema.json:
# for every read-only query method on the vSAN managed objects (and the host-side vSAN systems),
# the result type and every leaf field path with its type. This is the API schema, not live data.
import os, re, json
from pyVmomi import VmomiSupport as V, vim

MOS = {  # managed object type -> how it is reached
    "vim.cluster.VsanVcClusterConfigSystem": "vsan-cluster-config-system",
    "vim.cluster.VsanVcClusterHealthSystem": "vsan-cluster-health-system",
    "vim.cluster.VsanSpaceReportSystem": "vsan-cluster-space-report-system",
    "vim.cluster.VsanObjectSystem": "vsan-cluster-object-system",
    "vim.cluster.VsanPerformanceManager": "vsan-performance-manager",
    "vim.cluster.VsanVcDiskManagementSystem": "vsan-disk-management-system",
    "vim.cluster.VsanVcStretchedClusterSystem": "vsan-stretched-cluster-system",
    "vim.cluster.VsanIscsiTargetSystem": "vsan-cluster-iscsi-target-system",
    "vim.vsan.VsanFileServiceSystem": "vsan-cluster-file-service-system",
    "vim.cluster.VsanCapabilitySystem": "vsan-vc-capability-system",
    "vim.vsan.VsanRemoteDatastoreSystem": "vsan-remote-datastore-system",
    "vim.cluster.VsanClusterPowerSystem": "vsan-cluster-power-system",
    "vim.vsan.VsanIoInsightManager": "vsan-cluster-ioinsight-manager",
    "vim.cluster.VsanVcClusterResourceCheckSystem": "vsan-cluster-resource-check-system",
    "vim.host.VsanSystem": "HostSystem.configManager.vsanSystem",
    "vim.host.VsanInternalSystem": "HostSystem.configManager.vsanInternalSystem",
}
READ = re.compile(r"^(Vsan|Query|Get|Retrieve)|Query|Get", re.I)
WRITE = re.compile(r"Set|Update|Reconfig|Remove|Delete|Create|Add|Start|Stop|Repair|Upgrade|Rebalance|Enter|Exit|Mount|Unmount|Init|Claim|Upload|Download|Attach|Send|Run|Purge|Apply|Cancel|Perform|Clear|Toggle|Restore|Reset|Enable|Disable|Rekey|Prepare|Abort|Shutdown|Power|Relayout|Evacuat|Validate|Rename|Install|Modify|Configure|Destroy|Recover|Unlock|Log", re.I)
NUM = {"int", "long", "short", "byte", "float", "double"}


def tname(t):
    return V.GetVmodlName(t) if hasattr(t, "__name__") else str(t)


def walk(t, p, out, seen):
    item = getattr(t, "Item", None)
    if item is not None:
        return walk(item, p + "[]", out, seen)
    n = tname(t)
    props = getattr(t, "_propList", None)
    if props is None or issubclass(t, vim.ManagedObject):
        out[p] = "MoRef" if props is not None or n.startswith("vim.") and "." in n and n[4:5].isupper() else n
        return
    if n in seen or len(seen) > 10:
        out[p] = f"{n} (recursive)"
        return
    for pi in props:
        if pi.name in ("dynamicType", "dynamicProperty"):
            continue
        walk(pi.type, f"{p}.{pi.name}" if p else pi.name, out, seen | {n})


R = {}
for mo, how in MOS.items():
    try:
        T = V.GetVmodlType(mo)
    except Exception as e:
        R[mo] = {"_err": str(e)}
        continue
    for mi in T._methodInfo.values():
        w = mi.wsdlName
        if not READ.search(w) or WRITE.search(w.replace("Query", "").replace("Get", "")) or w.endswith("_Task") and "Query" not in w:
            continue
        res = mi.result
        fields = {}
        if res is not type(None) and tname(res) not in ("void", "vim.Task"):
            walk(res, "", fields, set())
        R[f"{mo}.{w}"] = {"reachedVia": how, "result": tname(res),
                          "params": [f"{p.name}: {tname(p.type)}" for p in (mi.params or [])],
                          "privilege": mi.privId, "fields": fields}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw", "schema.json")
json.dump(R, open(out, "w"), indent=1, sort_keys=True)
print("methods", len(R), "leaf fields", sum(len(v.get("fields", {})) for v in R.values()))
for k, v in sorted(R.items()):
    print(f"{k}  -> {v.get('result')}  ({len(v.get('fields', {}))} fields)")
