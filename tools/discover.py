# Prints what vSAN exists in the lab: counts and configuration shape only, no names.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import *

print("vCenter", content.about.fullName)
print("vSAN managed objects:", sorted(vsan))
cl = vsan_clusters()
print("clusters total", len(objects(vim.ClusterComputeResource)), "vSAN-enabled", len(cl))
for i, c in enumerate(cl):
    cfg = vsan["vsan-cluster-config-system"].VsanClusterGetConfig(cluster=c)
    hosts = c.host
    print(f"cluster#{i} hosts={len(hosts)}",
          "esa=", getattr(cfg, "vsanEsaEnabled", None),
          "dedup=", getattr(getattr(cfg, "dataEfficiencyConfig", None), "dedupEnabled", None),
          "compression=", getattr(getattr(cfg, "dataEfficiencyConfig", None), "compressionEnabled", None),
          "perfsvc=", getattr(getattr(cfg, "perfsvcConfig", None), "enabled", None),
          "stretched/2node=", bool(getattr(cfg, "vsanWitnessConfig", None)))
    for j, h in enumerate(hosts[:1]):
        print(f"  host#{j} esx", h.config.product.version, h.config.product.build)
print("vsanDatastores", sum(1 for d in objects(vim.Datastore) if d.summary.type == "vsan"))
