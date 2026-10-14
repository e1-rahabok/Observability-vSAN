"""Read-only vSphere and vSAN API clients for the lab.

All lab values (VC_HOST, VC_USER, VCPW) come from environment variables; run tools/env.ps1 first,
which loads them from the git-ignored .secrets/lab.env. Requires pyVmomi 8+ (includes the vSAN bindings).

  si      vSphere ServiceInstance (vim25 SOAP API)
  content si.RetrieveContent()
  vsan    dict of vSAN managed objects on vCenter, for example vsan["vsan-performance-manager"]
  rest    get(path) for the vCenter REST API (/api/...)
"""
import os, ssl, json, base64, urllib.request
from pyVim.connect import SmartConnect
from pyVmomi import vim
import vsanapiutils

VC_HOST, VC_USER, VCPW = os.environ["VC_HOST"], os.environ["VC_USER"], os.environ["VCPW"]
ctx = ssl._create_unverified_context()

si = SmartConnect(host=VC_HOST, user=VC_USER, pwd=VCPW, sslContext=ctx)
content = si.RetrieveContent()
vsan = vsanapiutils.GetVsanVcMos(si._stub, context=ctx,
                                 version=vsanapiutils.GetLatestVmodlVersion(VC_HOST))

_rest_hdr = {}


def rest(path):
    """GET a vCenter REST API path; returns parsed JSON or {"_err": status}."""
    if not _rest_hdr:
        r = urllib.request.Request(f"https://{VC_HOST}/api/session", method="POST", headers={
            "Authorization": "Basic " + base64.b64encode(f"{VC_USER}:{VCPW}".encode()).decode()})
        _rest_hdr["vmware-api-session-id"] = json.loads(urllib.request.urlopen(r, context=ctx).read())
    try:
        req = urllib.request.Request(f"https://{VC_HOST}{path}", headers=_rest_hdr)
        return json.loads(urllib.request.urlopen(req, context=ctx, timeout=60).read())
    except urllib.error.HTTPError as e:
        return {"_err": e.code}


def objects(vimtype):
    """All inventory objects of a vim type, for example vim.ClusterComputeResource."""
    view = content.viewManager.CreateContainerView(content.rootFolder, [vimtype], True)
    try:
        return list(view.view)
    finally:
        view.Destroy()


def vsan_clusters():
    """Clusters with vSAN enabled."""
    return [c for c in objects(vim.ClusterComputeResource)
            if c.configurationEx.vsanConfigInfo and c.configurationEx.vsanConfigInfo.enabled]


def paths(o, p="", out=None, numeric_only=False, depth=0):
    """Leaf field paths of a pyVmomi data object or JSON value (values discarded)."""
    out = set() if out is None else out
    if depth > 12:
        return out
    if isinstance(o, vim.ManagedObject):
        out.add(p + " <MoRef>")
    elif hasattr(o, "_propList") or isinstance(o, dict):
        items = o.items() if isinstance(o, dict) else ((pi.name, getattr(o, pi.name, None)) for pi in o._propList)
        for k, v in items:
            if k in ("dynamicType", "dynamicProperty"):
                continue
            paths(v, f"{p}.{k}" if p else k, out, numeric_only, depth + 1)
    elif isinstance(o, (list, tuple)):
        for v in o:
            paths(v, p + "[]", out, numeric_only, depth + 1)
    elif o is None:
        pass
    elif not numeric_only or (isinstance(o, (int, float)) and not isinstance(o, bool)):
        out.add(p)
    return out
