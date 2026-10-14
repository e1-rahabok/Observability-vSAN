# Downloads the documentation sources listed below into .cache/docs/ (git-ignored) and extracts
# identifiers only (metric names, API IDs, entity types, VCF Operations metric/property keys, chart names)
# into raw/docs.json. Descriptions are not copied. Re-run to refresh:  python tools/docs.py
import os, re, json, html, hashlib, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CACHE = os.path.join(ROOT, ".cache", "docs")
TD = "https://techdocs.broadcom.com/us/en/vmware-cis/vcf/vcf-9-0-and-later/9-1/"
MON = TD + "vsan-deployment-administration-and-monitoring/vsan-monitoring-and-troubleshooting/"
OPSM = TD + "infrastructure-operations/metric-property-and-alert-definitions/metrics-definitions-in-vrealize-operations-manager/vsan-metrics/"
OPSP = TD + "infrastructure-operations/metric-property-and-alert-definitions/property-definitions-in-vrealize-operations-manager/vsan-properties/"

# kind: kb (KB tables with API IDs), ops-metric / ops-property (VCF Operations reference), manual / blog (text)
SOURCES = [
    ("kb", "KB 326953: vSAN Performance Graphs in the vSphere Web Client Part 1", "https://knowledge.broadcom.com/external/article/326953"),
    ("kb", "KB 326812: vSAN Performance Graphs in the vSphere Web Client Part 2", "https://knowledge.broadcom.com/external/article/326812"),
    ("kb-health", "KB 326438: vSAN Health Service Check Information", "https://knowledge.broadcom.com/external/article/326438"),
    ("kb", "KB 326673: vSAN performance diagnostics: congestion in disk groups", "https://knowledge.broadcom.com/external/article/326673"),
] + [("manual", "VCF 9.1 vSAN: " + p.split("/")[-1][:-5].replace("-", " "), MON + p) for p in [
    "monitor-virtual-san-performance/about-the-vsan-performance-service.html",
    "monitor-virtual-san-performance/view-vsan-cluster-performance.html",
    "monitor-virtual-san-performance/view-vsan-host-performance.html",
    "monitor-virtual-san-performance/view-virtual-san-vm-performance.html",
    "monitor-virtual-san-performance/use-vsan-i-o-insight.html",
    "monitor-the-vsan-cluster/monitor-vsan-capacity.html",
    "monitor-the-vsan-cluster/about-reserved-capacity-in-vsan-cluster.html",
    "monitor-the-vsan-cluster/about-vsan-cluster-resynchronization.html",
    "monitor-the-vsan-cluster/monitor-physical-disks-in-vsan-cluster.html",
    "monitor-the-vsan-cluster/monitor-virtual-disks-in-vsan-cluster.html",
    "monitor-the-vsan-cluster/monitor-vsan-esa-capacity/vsan-esa-effective-capacity.html",
    "monitor-the-vsan-cluster/monitor-vsan-esa-capacity/monitor-vsan-esa-legacy-capacity(1).html",
    "monitor-the-vsan-cluster/using-the-vsan-default-alarms/view-vsan-default-alarms.html",
    "monitor-the-vsan-cluster/using-the-vsan-default-alarms/view-vsan-network-alarms.html",
    "monitoring-vsan-skyline-health/about-the-vsan-skyline-health.html",
    "monitoring-vsan-skyline-health/check-vsan-skyline-health.html",
]] + [("ops-metric", "VCF Operations 9.1: " + p[:-5].replace("-", " "), OPSM + p) for p in [
    "metrics-for-vsan-cluster.html", "metrics-for-vsan-datastore.html", "metrics-for-vsan-enabled-host.html",
    "metrics-for-vsan-fault-domain-resource-kind.html", "disk-i-o-and-disk-space-metrics-for-vsan-disk-groups.html",
    "read-cache-metrics-for-vsan-disk-groups.html", "write-buffer-metrics-for-vsan-disk-groups.html",
    "cache-de-stage-metrics-for-vsan-disk-groups.html", "congestion-metrics-for-vsan-disk-groups.html",
    "resync-traffic-metrics-for-vsan-disk-groups.html", "metrics-for-vsan-storage-pool.html",
    "metrics-for-vsan-cache-disk.html", "metrics-for-vsan-capacity-disk.html", "metrics-for-vsan-esa-disk.html",
    "metrics-for-vsan-file-server.html", "metrics-for-vsan-file-share.html", "metrics-for-vsan-world.html",
    "capacity-model-for-vsan-objects.html",
]] + [("ops-property", "VCF Operations 9.1: " + p[:-5].replace("-", " "), OPSP + p) for p in [
    "properties-for-vsan-cluster.html", "properties-for-vsan-enabled-host.html", "properties-for-vsan-disk-groups.html",
    "properties-for-vsan-storage-pool.html", "properties-for-vsan-cache-disk.html", "properties-for-vsan-capacity-disk.html",
    "properties-for-vsan-esa-disk.html", "properties-for-vsan-file-server.html", "properties-for-vsan-file-share.html",
]] + [
    ("blog", "Blog: Effective Capacity View in vSAN for VCF 9.1", "https://blogs.vmware.com/cloud-foundation/2026/05/11/effective-capacity-view-in-vsan-for-vcf-9-1/"),
    ("blog", "Blog: Global Deduplication in vSAN ESA for VCF 9.0", "https://blogs.vmware.com/cloud-foundation/2025/06/19/global-deduplication-in-vsan-esa-for-vmware-cloud-foundation-9-0/"),
    ("blog", "Blog: Understanding the different levels of vSAN performance metrics", "https://blogs.vmware.com/cloud-foundation/2019/06/12/performance-troubleshooting-understanding-the-different-levels-of-vsan-performance-metrics/"),
]


def get(url):
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")
    if not os.path.exists(f):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            open(f, "wb").write(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:
            return None, str(e)
    return open(f, encoding="utf-8", errors="ignore").read(), None


def text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def cells(row):
    return re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)


def split_cell(c):
    """A VCF Operations cell may hold several keys separated by <br>, <p> or <li>."""
    parts = re.split(r"<br\s*/?>|</p>|</li>|\n", c)
    return [t for t in (text(p) for p in parts) if t]


def main_html(h):
    """The article body: after the site banner, before the footer and "Related" links."""
    h = re.sub(r"<script.*?</script>|<style.*?</style>|<nav.*?</nav>", "", h, flags=re.S)
    i = h.find("binaries for components")
    h = h[i:] if i >= 0 else h
    ends = [j for j in (h.find(m) for m in ("<footer", "Was this", "Related")) if j > 0]
    return h[:min(ends)] if ends else h


out = []
for kind, title, url in SOURCES:
    h, err = get(url)
    src = {"kind": kind, "title": title, "url": url, "items": []}
    if err:
        src["error"] = err
        out.append(src)
        continue
    body = main_html(h)
    if text(body).startswith("404") or "Page Not Found" in body[:3000]:
        src["error"] = "page not found"
    tables = re.findall(r"<table.*?</table>", body, re.S)
    for t in tables:
        rows = re.findall(r"<tr.*?</tr>", t, re.S)
        if not rows:
            continue
        head = [text(c).lower() for c in cells(rows[0])]
        for r in rows[1:]:
            cs = cells(r)
            if len(cs) != len(head):
                continue
            row = dict(zip(head, cs))
            if kind == "kb":
                api = next((k for k in head if "api" in k), None)
                if not api:
                    continue
                ent = next((k for k in head if k.startswith("corresponding entity")), None)
                rt = next((k for k in head if "real-time" in k), None)
                src["items"].append({"metric": text(cs[0]), "apiId": text(row[api]),
                                     "entityType": text(row[ent]) if ent else "",
                                     "realtimeEntityType": text(row[rt]) if rt else ""})
            else:
                key = next((k for k in head if k in ("metrics", "metric", "metric name", "properties", "property", "property name", "name")), head[-1] if len(head) == 2 else head[0])
                grp = head[0] if head[0] != key else None
                for k in split_cell(row[key]):
                    src["items"].append({"key": k, "group": text(row[grp]) if grp else ""})
    if kind == "kb-health":
        res = h[h.find(">Resolution<"):h.find(">Additional Information<")]
        for grp, sec in re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>(.*?)(?=<h[2-4]|$)", res, re.S):
            for li in re.findall(r"<li[^>]*>(.*?)</li>", sec, re.S):
                k = text(li)
                ver = re.search(r"\(([^()]*(?:and higher|Deprecated|only)[^()]*)\)", k)
                link = re.search(r'href="([^"]+)"', li)
                src["items"].append({"group": text(grp), "key": k, "version": ver.group(1) if ver else "",
                                     "url": link.group(1) if link else ""})
    if kind.startswith("ops-") and not src["items"]:
        for li in re.findall(r"<li[^>]*>(.*?)</li>", body, re.S):
            k = text(re.split(r"<p|<br|<ul", li, maxsplit=1)[0]) or text(li)
            if k and len(k) <= 120:
                src["items"].append({"key": k, "group": ""})
    if kind == "manual":
        # keep the term only: "Swap objects - Usage of VM swap files." -> "Swap objects"; drop descriptions
        for i in src["items"]:
            k = re.sub(r"^Displays the following:\s*", "", i["key"])
            i["key"] = k.split(" - ")[0] if " - " in k and len(k.split(" - ")[0]) < 60 else ""
    if kind in ("manual", "blog", "kb"):
        src["headings"] = [text(x) for x in re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", body, re.S)][:60]
    out.append(src)
    print(f"{kind:12} items={len(src['items']):4} {'ERR ' + src['error'] if src.get('error') else ''} {title}")

json.dump(out, open(os.path.join(ROOT, "raw", "docs.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
