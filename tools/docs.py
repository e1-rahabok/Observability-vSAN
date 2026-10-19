# Downloads the documentation sources listed below into .cache/docs/ (git-ignored) and extracts
# identifiers only (metric names, API IDs, entity types, VCF Operations metric/property keys, chart names)
# into raw/docs.json. Descriptions are not copied. Re-run to refresh:  python tools/docs.py
# Pages are cached; delete .cache/docs/ to pick up new blog posts. Run after tools/catalog.py (the scan uses its names).
import os, re, json, html, hashlib, shutil, subprocess, urllib.request

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
# Added after the first set: more KBs with API IDs (kb), a KB without them (kb-scan), VMware technical papers (guide)
KBA = "https://knowledge.broadcom.com/external/article/"
SOURCES[4:4] = [
    ("kb", "KB 326720: vSAN Performance Graphs in the vSphere Web Client Part 3", KBA + "326720"),
    ("kb", "KB 326555: vSAN PMem Performance Graphs in vSphere Web Client", KBA + "326555"),
    ("kb-scan", "KB 326479: Understanding Congestion in vSAN", KBA + "326479"),
]
SOURCES[-3:-3] = [("guide", t, "https://www.vmware.com/docs/" + p) for t, p in [
    ("Troubleshooting vSAN Performance", "vmw-troubleshooting-vsan-performance"),
    ("vSAN Proof of Concept: vSAN Performance Testing", "vsan-proof-of-concept-vsan-performance-testing"),
    ("vSAN Proof of Concept: Management, Monitoring and Hardware Testing", "8-0u2-vsan-management-monitoring-hardware-testing"),
    ("vSAN Proof of Concept: vSAN Architecture Overview and Setup", "8-0u2-vsan-architectureoverviewsetup"),
    ("vSAN Proof of Concept: vSAN Features", "8-0u2-vsan-features-2"),
    ("vSAN Operations Guide", "vmw-vsan-operations-guide"),
    ("vSAN Design Guide", "vmware-vsan-design-guide"),
    ("vSAN Space Efficiency Technologies", "vmw-vsan-space-efficiency"),
    ("vSAN Performance Evaluation Checklist", "vmw-vsan-performance-evaluation-checklist"),
    ("vSAN File Services", "vmw-vsan-file-services"),
    ("Design and Operational Guidance for vSAN Storage Clusters", "vmw-vsan-storage-clusters-design-and-operations"),
    ("vSAN Frequently Asked Questions", "vmw-vsan-faqs"),
]]

# Blogs searched in full: every post found is scanned for vSAN chart and metric names; posts that name at least two
# (or one API metric ID or entity type) become sources. WordPress sites by their search API, the VMware blog by sitemap.
BLOGS = [
    ("Yellow Bricks", "wp", "https://www.yellow-bricks.com"),
    ("Cormac Hogan", "wp", "https://cormachogan.com"),
    ("William Lam", "wp", "https://williamlam.com"),
    ("VMware VCF blog", "sitemap", "https://blogs.vmware.com/cloud-foundation/post-sitemap.xml"),
    ("VMware VCF blog", "sitemap", "https://blogs.vmware.com/cloud-foundation/post-sitemap2.xml"),
]
SLUG = re.compile(r"vsan|virtual-san|hci|hyperconverged|storage|esa-|dedup|compression|capacity|resync|stretched|"
                  r"witness|2-node|two-node|perf|latency|congestion|vsantop|iops|raid|erasure|snapshot|file-serv|iscsi")
PDFTOTEXT = shutil.which("pdftotext") or next((p for p in (r"C:\Program Files\Git\ucrt64\bin\pdftotext.exe",
                                                          r"C:\Program Files\Git\mingw64\bin\pdftotext.exe") if os.path.exists(p)), None)


def get(url):
    """Page text from the cache, downloading it first if needed. PDFs are converted with pdftotext."""
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")
    if not os.path.exists(f):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            open(f, "wb").write(urllib.request.urlopen(req, timeout=120).read())
        except Exception as e:
            return None, str(e)
    if open(f, "rb").read(5) == b"%PDF-":
        if not os.path.exists(f + ".txt"):
            if not PDFTOTEXT:
                return None, "pdftotext not found"
            subprocess.run([PDFTOTEXT, "-q", "-enc", "UTF-8", f, f + ".txt"], check=True)
        return html.escape(open(f + ".txt", encoding="utf-8", errors="ignore").read()), None
    return open(f, encoding="utf-8", errors="ignore").read(), None


def norm(s):
    """Lower case, I/O -> io, & -> and, punctuation dropped, plural s dropped, so "Congestions" matches "congestion"."""
    s = s.lower().replace("i/o", "io").replace("&", " and ")
    s = re.sub(r"[^a-z0-9% ]", " ", s)
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in s.split())


def vocabulary():
    """Chart and metric names (two words or more, minus the generic ones), metric IDs and entity types from the API."""
    cat = json.load(open(os.path.join(ROOT, "raw", "catalog.json")))
    lp = os.path.join(ROOT, "raw", "live.json")
    live = json.load(open(lp)) if os.path.exists(lp) else {"perf": {}}
    skip = {norm(x) for x in ["capacity and usage", "mean latency", "request count", "net stats", "batch stats",
                              "gen num", "requests per second", "total memory used", "read iops", "write iops",
                              "read latency", "write latency", "read throughput", "write throughput", "total iops",
                              "total latency", "total throughput", "space efficiency", "inbound stats",
                              "outbound stats", "lock wait count", "read io", "write io"]}
    names, ids = {}, {}
    for e in cat["perf entity types"]:
        if "-" in e["name"]:
            ids[e["name"]] = "entity"
        for tier in ("graphs", "advancedGraphs", "verboseGraphs", "hotspotGraphs"):
            for g in e[tier]:
                for n, k in [(g["name"], "chart")] + [(m["name"], "metric") for m in g["metrics"]]:
                    if n and len(norm(n).split()) >= 2 and norm(n) not in skip:
                        names.setdefault(norm(n), (n, k))
                for m in g["metrics"]:
                    ids.setdefault(m["label"], "metric ID")
    for v in live["perf"].values():
        for l in v.get("unlisted", []):
            ids.setdefault(l, "metric ID")
    ids = {k: v for k, v in ids.items() if v == "entity" or (len(k) >= 6 and re.search(r"[a-z][A-Z]", k))}
    return ([(re.compile(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])"), name, k) for n, (name, k) in names.items()],
            [(re.compile(r"(?<![\w-])" + re.escape(i) + r"(?![\w-])"), i, k) for i, k in ids.items()])


VOCAB = vocabulary()


def scan(body):
    """Names and IDs from the API vocabulary that occur in a page; nothing else is kept."""
    t = html.unescape(re.sub(r"<[^>]+>", " ", body))
    n = norm(t)
    found = [{"key": name, "match": k} for p, name, k in VOCAB[0] if p.search(n)]
    ids = [{"key": i, "match": k} for p, i, k in VOCAB[1] if p.search(t)]
    # A metric ID alone may be an ordinary API field of the same name (iopsLimit in a storage policy); keep it only
    # when the page is about the performance service
    if not any(i["match"] == "entity" for i in ids) and "VsanPerf" not in t:
        ids = [i for i in ids if i["match"] != "metric ID"]
    return found + ids


def blog_posts():
    """(blog, title, url, date, body) for every post the blog search or sitemap returns, and per-blog counts."""
    for blog, how, base in BLOGS:
        if how == "wp":
            page = 1
            while True:
                h, err = get(f"{base}/wp-json/wp/v2/posts?search=vsan&per_page=20&page={page}&_fields=link,title,date,content")
                if err or not h.strip().startswith("[") or h.strip() == "[]":
                    break
                for p in json.loads(h):
                    yield blog, text(p["title"]["rendered"]), p["link"], p["date"][:10], p["content"]["rendered"]
                page += 1
        else:
            h, err = get(base)
            for u in re.findall(r"<loc>([^<]+)</loc>", h or ""):
                if not SLUG.search(u.rstrip("/").split("/")[-1]):
                    continue
                p, err = get(u)
                if err:
                    continue
                title = text((re.search(r"<h1[^>]*>(.*?)</h1>", p, re.S) or re.search(r"<title>(.*?)</title>", p, re.S) or [0, ""])[1])
                d = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", u)
                yield blog, title, u, "-".join(d.groups()) if d else "", post_body(p)


def text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def cells(row):
    return re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)


def split_cell(c):
    """A VCF Operations cell may hold several keys separated by <br>, <p> or <li>. Line breaks in the HTML source
    are not separators: techdocs wraps long keys ("vSAN|Read\\n Cache|Read Throughput (KBps)")."""
    parts = re.split(r"<br\s*/?>|</p>|</li>", c)
    return [t for t in (text(p) for p in parts) if t]


def main_html(h):
    """The article body: after the site banner, before the footer and "Related" links."""
    h = re.sub(r"<script.*?</script>|<style.*?</style>|<nav.*?</nav>", "", h, flags=re.S)
    i = h.find("binaries for components")
    h = h[i:] if i >= 0 else h
    ends = [j for j in (h.find(m) for m in ("<footer", "Was this", "Related")) if j > 0]
    return h[:min(ends)] if ends else h


def post_body(p):
    """A VMware blog post without the page frame and the related-posts list."""
    i, j = p.find('class="entry-content"'), p.find("related-posts")
    return p[i:j if j > i else None] if i >= 0 else p


SCANNED = ("kb-scan", "guide", "blog")
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
    if kind in SCANNED:
        src["items"] = scan(post_body(h) if kind == "blog" else h if kind == "guide" else body)
    tables = re.findall(r"<table.*?</table>", body, re.S) if kind not in SCANNED else []
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
                    if k.endswith("."):  # a note in the key column, not a key
                        continue
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
    if kind in ("manual", "kb"):
        src["headings"] = [text(x) for x in re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", body, re.S)][:60]
    out.append(src)
    print(f"{kind:12} items={len(src['items']):4} {'ERR ' + src['error'] if src.get('error') else ''} {title}")

# Blog search: keep posts that name at least two charts or metrics, or one metric ID or entity type
known, stats = {s["url"] for s in out}, {}
for blog, title, url, date, body in blog_posts():
    st = stats.setdefault(blog, {"kind": "scan", "title": blog, "url": "", "posts": 0, "kept": 0, "items": []})
    if url in known:
        continue
    known.add(url)
    st["posts"] += 1
    items = scan(body)
    if sum(i["match"] in ("chart", "metric") for i in items) >= 2 or any(i["match"] in ("metric ID", "entity") for i in items):
        st["kept"] += 1
        out.append({"kind": "blog", "title": f"{blog}: {title}", "url": url, "date": date, "items": items})
for st in stats.values():
    out.append(st)
    print(f"scan         posts={st['posts']:4} kept={st['kept']:3} {st['title']}")

json.dump(out, open(os.path.join(ROOT, "raw", "docs.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
