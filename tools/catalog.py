# Dumps the catalogs the vSAN services publish (no cluster needed, no instance data) to raw/catalog.json:
#   - vSAN performance service: entity types, graphs, metrics (label, unit, description)
#   - vSAN health service: all supported health checks (group, test id, name, description)
#   - vCenter PerformanceManager counters whose group mentions vSAN
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *

R = {}
perf = vsan["vsan-performance-manager"]
ents = perf.VsanPerfGetSupportedEntityTypes()
M = lambda m: {k: getattr(m, k, None) for k in ("label", "name", "group", "rollupType", "statsType", "description", "metricsCollectInterval")}
G = lambda g: {"id": g.id, "name": getattr(g, "name", None), "unit": getattr(g, "unit", None),
               "description": getattr(g, "description", None), "metrics": [M(m) for m in (g.metrics or [])]}
R["perf entity types"] = [{"name": e.name, "id": getattr(e, "id", None), "description": getattr(e, "description", None),
                           **{k: [G(g) for g in (getattr(e, k, None) or [])]
                              for k in ("graphs", "advancedGraphs", "verboseGraphs", "hotspotGraphs")}}
                          for e in ents]

health = vsan["vsan-cluster-health-system"]
try:
    checks = health.VsanQueryAllSupportedHealthChecks()
    R["health checks"] = [{"groupId": c.groupId, "groupName": c.groupName, "testId": c.testId, "testName": c.testName}
                          for c in checks]
except Exception as e:
    R["health checks"] = {"_err": f"{type(e).__name__}: {str(e)[:200]}"}

pm = content.perfManager
R["vc perf counters (vsan groups)"] = sorted(
    {f"{c.groupInfo.key}.{c.nameInfo.key}.{c.rollupType} [{c.unitInfo.key}] {c.nameInfo.summary}"
     for c in pm.perfCounter if "vsan" in c.groupInfo.key.lower()})

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw", "catalog.json")
json.dump(R, open(out, "w"), indent=1, default=str)
print("perf entity types", len(R["perf entity types"]),
      "metrics", len({(e["name"], m["label"]) for e in R["perf entity types"]
           for k in ("graphs", "advancedGraphs", "verboseGraphs", "hotspotGraphs") for g in e[k] for m in g["metrics"]}))
print("health checks", len(R["health checks"]) if isinstance(R["health checks"], list) else R["health checks"])
print("vc perf counters", len(R["vc perf counters (vsan groups)"]))
print([e["name"] for e in R["perf entity types"]])
