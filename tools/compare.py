# Builds metrics-docs.md, properties-docs.md and comparison.md from raw/docs.json, raw/catalog.json, raw/schema.json.
# Run after tools/docs.py and tools/build.py:  python tools/compare.py
import os, re, json, difflib, collections
import importlib.util

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
spec = importlib.util.spec_from_file_location("build", os.path.join(ROOT, "tools", "build.py"))
cat = json.load(open(os.path.join(ROOT, "raw", "catalog.json")))
sch = json.load(open(os.path.join(ROOT, "raw", "schema.json")))
docs = json.load(open(os.path.join(ROOT, "raw", "docs.json"), encoding="utf-8"))

# Reuse the entity -> object type map from build.py without regenerating its output
src_build = open(os.path.join(ROOT, "tools", "build.py"), encoding="utf-8").read()
ns = {}
exec(src_build[src_build.index("TYPES = "):src_build.index("PUNIT = ")], {"re": re}, ns)
TYPES, ENT2TYPE = ns["TYPES"], ns["ENT2TYPE"]
ENT2TYPE.update({"ioinsight-histogram": "Virtual Machine"})

CODE = {"kb": "KB", "kb-health": "KB", "manual": "MAN", "ops-metric": "OPS", "ops-property": "OPS", "blog": "BLOG"}
SRCNUM = {}
for i, s in enumerate(docs, 1):
    SRCNUM[s["url"]] = i


def ref(s):
    return f"[{SRCNUM[s['url']]}]"


def esc(x):
    return (x or "").replace("|", "\\|").strip()


# VCF Operations pages -> object type
OPS_TYPE = [("vsan cluster", "vSAN Cluster"), ("vsan datastore", "vSAN Datastore"), ("vsan enabled host", "vSAN Host"),
            ("fault domain", "vSAN Host"), ("disk group", "Disk Group"), ("storage pool", "Disk Group"),
            ("cache disk", "vSAN Disk"), ("capacity disk", "vSAN Disk"), ("esa disk", "vSAN Disk"),
            ("file server", "File Share"), ("file share", "File Share"), ("vsan world", "vSAN Cluster"),
            ("capacity model", "vSAN Cluster")]


def ops_type(title):
    t = title.lower()
    return next(v for k, v in OPS_TYPE if k in t)


def ops_note(title):
    t = title.lower()
    for k in ("fault domain", "storage pool", "cache disk", "capacity disk", "esa disk", "file server", "vsan world", "capacity model"):
        if k in t:
            return "VCF Operations object: " + k.title().replace("Esa", "ESA")
    return ""


# ---------- performance metrics: KB vs API
api_perf = {}
for e in cat["perf entity types"]:
    for tier in ("graphs", "advancedGraphs", "verboseGraphs", "hotspotGraphs"):
        for g in e[tier]:
            for m in g["metrics"]:
                api_perf.setdefault((e["name"], m["label"]), (m["name"], tier))


def kb_rows():
    """(entity, label, metric name, realtime entity, source) with 'A or B' entities and 'r/w' label pairs expanded."""
    for s in docs:
        if s["kind"] != "kb":
            continue
        for i in s["items"]:
            ents = [x.strip() for x in i["entityType"].split(" or ") if x.strip()]
            raw = re.sub(r"\s+\S+$", "", i["apiId"]) if " " in i["apiId"] else i["apiId"]
            labels = [x.strip() for x in raw.split("/") if x.strip()]
            for e in ents:
                for l in labels:
                    yield e, l, i["metric"], i["realtimeEntityType"], s


kb = list(kb_rows())
kb_set = {(e, l) for e, l, *_ in kb}
kb_only = sorted({(e, l) for e, l in kb_set if (e, l) not in api_perf})
api_only = sorted(k for k in api_perf if k not in kb_set)
matched = sorted(kb_set & set(api_perf))

# ---------- health checks: KB index vs API catalog
api_hc = cat["health checks"]
kbh_src = next(s for s in docs if s["kind"] == "kb-health")


def norm_hc(t):
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"^(vSAN( Skyline)? Health( Service)?|vSAN health|vSAN --|vLCM Upgrade Precheck)\s*[-–:]+\s*", "", t, flags=re.I)
    t = re.sub(r"^[^-–]{2,45}\s[-–]+\s", "", t)  # drop "<group> - "
    t = re.sub(r"\btestID:.*|com\.vmware\.\S+|<==.*", "", t)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t.lower()).split())


kbh = [(i, norm_hc(i["key"])) for i in kbh_src["items"] if i["key"]]
STOP = {"vsan", "the", "is", "are", "check", "health", "for", "on", "of", "and", "a", "to", "in", "with", "all", "hosts", "host"}
SYN = [(r"vc", "vcenter"), (r"hcl", "certified"), (r"vmware certified|vsan certified", "certified"),
       (r"kms|key management servers?", "kms"), (r"aes ni", "aesni")]


def toks(t):
    for a, b in SYN:
        t = re.sub(a, b, t)
    return {w for w in t.split() if w not in STOP}


# Pairs confirmed by reading both names, where wording differs too much for automatic matching (testId -> KB key prefix)
OVERRIDE = {
    "kmsconnection": "vSAN Health Service - Encryption - Key Management Servers Connection Check",
    "hostcpuaesni": "vSAN Health Service - Encryption - CPU AES-NI Host Enablement Check",
    "ditconfig": "Data-in-transit encryption - Configuration check",
    "limit1hf": "vSAN Health Service - Limits Health – After one additional host failure",
    "nodecomponentlimit": "vSAN Health Service - Limits - Host component",
    "controlleronhcl": "vSAN Health Service - vSAN HCL health – SCSI controller on vSAN HCL",
    "controllerreleasesupport": "vSAN Health Service - vSAN HCL health - Controller release support",
    "controllerdriver": "vSAN Health Service - vSAN HCL health - Controller driver",
    "controllerfirmware": "vSAN Health Service - Hardware Compatibility - Controller Firmware Check",
    "controllerdiskmode": "vSAN Health Service - Hardware Compatibility - Disk Group Type Check",
    "pniclinkspeed": "vSAN Health Service - Hardware compatibility - Physical NIC link speed",
    "hclhostbadstate": "vSAN Health Service - HCL Health - Host issues retrieving hardware info",
    "mmdecominsync": "vSAN Host Maintenance Mode is in sync with vSAN Node Decommission State",
    "smallping": "vSAN Health Service - Network health - Hosts small ping test",
    "largeping": "vSAN Health Service - Network health - Hosts small ping test",  # one KB covers both
    "perfsvcstatus": "vSAN Health Service - Performance Service - Status Check",
    "dedupservice": None,  # no KB entry; automatic match to "data protection service" is wrong
}
hc_match, used, assigned = [], set(), set()
for h in api_hc:
    if h["testId"] not in OVERRIDE:
        continue
    pre = OVERRIDE[h["testId"]]
    j = next((j for j, (i, _) in enumerate(kbh) if pre and i["key"].startswith(pre)), None)
    if j is not None:
        hc_match.append((h, kbh[j][0], 1.0, "override"))
        used.add(j)
    assigned.add((h["groupId"], h["testId"]))
pairs = []
for h in api_hc:
    if (h["groupId"], h["testId"]) in assigned:
        continue
    n = norm_hc(h["testName"]); tn = toks(n)
    for j, (i, kn) in enumerate(kbh):
        tk = toks(kn)
        jac = len(tn & tk) / len(tn | tk) if tn | tk else 0
        pairs.append((max(difflib.SequenceMatcher(None, n, kn).ratio(), jac), (h["groupId"], h["testId"]), j, h))
for sc, tid, j, h in sorted(pairs, key=lambda x: -x[0]):
    if sc < 0.6:
        break
    if tid in assigned or j in used:
        continue
    hc_match.append((h, kbh[j][0], sc, "name"))
    used.add(j); assigned.add(tid)
matched_keys = {(m[0]["groupId"], m[0]["testId"]) for m in hc_match}
# A check listed in two groups (local and Online health) counts as documented if either copy matched
matched_ids = {k[1] for k in matched_keys}
hc_api_only = [h for h in api_hc if h["testId"] not in matched_ids]
hc_kb_only = [i for j, (i, _) in enumerate(kbh) if j not in used]

# ---------- capacity terms (manual) -> API fields (by name; not verified live)
CAP = {
    "Total usable capacity": "effectiveSpaceUsage.totalUsableB",
    "Free usable capacity": "effectiveSpaceUsage.freeUsableB",
    "Actually written": "effectiveSpaceUsage.actualWrittenB",
    "Object reserved": "effectiveSpaceUsage.overReservedB",
    "Total provisioned capacity": "effectiveSpaceUsage.totalProvisionB",
    "Data reduction ratio": "spaceEfficiencyRatio.overallRatio",
    "Deduplication ratio": "spaceEfficiencyRatio.dedupRatio",
    "Compression ratio": "spaceEfficiencyRatio.compressionRatio",
    "Thin provisioning saving ratio": "spaceEfficiencyRatio.thinProvisionRatio",
    "Snapshot saving ratio": "spaceEfficiencyRatio.snapshotSavingRatio",
    "Fully inflated snapshot capacity": "effectiveSpaceUsage.snapshotSpace.fullyInflatedSnapshotUsedB",
    "vSAN snapshot used capacity": "effectiveSpaceUsage.snapshotSpace.actualSnapshotUsedB",
    "Total Raw Capacity": "totalCapacityB",
    "Free space on disks": "freeCapacityB",
    "Used capacity": None, "Overprovisioning ratio": None, "RAID Factor": None, "System Usage": "spaceDetail.spaceUsageByObjectType[] (system object types)",
    "Used": "spaceOverview.usedB", "Reservations and Alerts": "capacityHealthThreshold.*",
}
space_fields = set(sch["vim.cluster.VsanSpaceReportSystem.VsanQuerySpaceUsage"]["fields"])

# ---------- docs tables
mrows, prows = {t: [] for t in TYPES}, {t: [] for t in TYPES}
for e, l, name, rt, s in kb:
    t = ENT2TYPE.get(e, "vSAN Cluster")
    note = f"Real-time entity `{rt}`" if rt else ""
    mrows[t].append(f"| {t} | {esc(name)} | KB {ref(s)} | `{e}` → `{l}` | {note} |")
for s in docs:
    if s["kind"] == "manual" and s["items"]:
        for i in s["items"]:
            name = i["group"] + (f": {i['key']}" if i["key"] else "")
            t = "vSAN Cluster"
            mrows[t].append(f"| {t} | {esc(name)} | MAN {ref(s)} | Capacity page term | |")
    elif s["kind"] in ("ops-metric", "ops-property"):
        t = ops_type(s["title"])
        rows = mrows if s["kind"] == "ops-metric" else prows
        for i in s["items"]:
            key = i["key"] if "|" in i["key"] or not i["group"] else f"{i['group']}|{i['key']}"
            rows[t].append(f"| {t} | {esc(key)} | OPS {ref(s)} | VCF Operations key | {ops_note(s['title'])} |")
for i in kbh_src["items"]:
    prows["vSAN Cluster"].append(f"| vSAN Cluster | Health: {esc(i['key'])} | KB {ref(kbh_src)} | Group: {esc(i['group'])} | {esc(i['version'])} |")

SRC_LIST = "\n".join(f"{SRCNUM[s['url']]}. {CODE[s['kind']]}: [{s['title']}]({s['url']})" + (f" (not retrieved: {s['error']})" if s.get("error") else "")
                     for s in docs)
LEG = """**Source legend**

| Code | Source |
|---|---|
| KB | Broadcom Knowledge Base article |
| MAN | VCF 9.1 vSAN documentation (techdocs.broadcom.com) |
| OPS | VCF 9.1 Operations metric and property reference (techdocs.broadcom.com). Keys are VCF Operations names, not vSAN API fields |
| BLOG | VMware blog (used in the comparison notes only) |

The number after the code refers to the source list at the end."""


def page(title, intro, header, rows):
    out = [f"# {title}", "", intro, "", LEG, "", header, "|" + "---|" * (header.count("|") - 1)]
    for t in TYPES:
        out += rows[t]
    out += ["", "## Sources", "", SRC_LIST]
    return "\n".join(out) + "\n"


open(os.path.join(ROOT, "metrics-docs.md"), "w", encoding="utf-8").write(page(
    "vSAN Metrics (Documentation)",
    "Generated by `tools/compare.py` from [raw/docs.json](raw/docs.json); do not edit by hand. Metric names and identifiers "
    "as published by Broadcom (KB articles, VCF 9.1 vSAN documentation, VCF Operations 9.1 reference). Descriptions are "
    "not copied; follow the source link.",
    "| Object Type | Metric | Source | Documented ID | Notes |", mrows))
open(os.path.join(ROOT, "properties-docs.md"), "w", encoding="utf-8").write(page(
    "vSAN Properties (Documentation)",
    "Generated by `tools/compare.py` from [raw/docs.json](raw/docs.json); do not edit by hand. Health checks come from "
    "the KB index of vSAN health checks; other properties from the VCF Operations 9.1 reference.",
    "| Object Type | Property | Source | Documented ID / group | Notes |", prows))

# ---------- comparison
by_ent_api_only = collections.Counter(e for e, _ in api_only)
kb_ents = {e for e, _ in kb_set}
L = []
L.append(f"""# vSAN: API vs Documentation

Compares what the vSAN API returns ([metrics-api.md](metrics-api.md), [properties-api.md](properties-api.md)) with what
Broadcom documents ([metrics-docs.md](metrics-docs.md), [properties-docs.md](properties-docs.md)). Generated by
`tools/compare.py`; the summary and notes at the top are in `tools/compare_notes.md`.

{open(os.path.join(ROOT, 'tools', 'compare_notes.md'), encoding='utf-8').read().strip()}

## 1. Performance metrics: KB 326953 and 326812 vs the live performance service

The two KBs are the only documents that give API metric IDs, so this is an exact match on `(entity type, metric label)`.

| | Count |
|---|---|
| Metrics listed live by `VsanPerfGetSupportedEntityTypes` | {len(api_perf)} |
| Metrics documented in the KBs | {len(kb_set)} |
| Documented and live | {len(matched)} |
| Documented but not listed live | {len(kb_only)} |
| Live but not documented in the KBs | {len(api_only)} |
| Live entity types with no KB coverage at all | {len({e for e, _ in api_perf} - kb_ents)} of {len({e for e, _ in api_perf})} |

### Documented but not listed live

| Entity type | Metric label | Likely reason |
|---|---|---|""")
for e, l in kb_only:
    why = ("Entity type not returned by `VsanPerfGetSupportedEntityTypes`" if e not in {x for x, _ in api_perf}
           else "Label not in this entity's live metric list")
    L.append(f"| `{e}` | `{l}` | {why} |")
L.append("""
### Live but not documented, by entity type

| Entity type | Object type | Undocumented metrics | Entity type in KBs? |
|---|---|---|---|""")
for e, n in sorted(by_ent_api_only.items(), key=lambda x: (ENT2TYPE.get(x[0], ""), x[0])):
    L.append(f"| `{e}` | {ENT2TYPE.get(e, '')} | {n} | {'yes' if e in kb_ents else 'no'} |")
L.append("\n<details><summary>Full list of live metrics not in the KBs</summary>\n\n| Entity type | Label | Name (from API) | Tier |\n|---|---|---|---|")
for e, l in api_only:
    n, tier = api_perf[(e, l)]
    L.append(f"| `{e}` | `{l}` | {esc(n)} | {tier.replace('Graphs', '').replace('graphs', 'default')} |")
L.append("\n</details>")

L.append(f"""
## 2. Health checks: KB 326438 index vs `VsanQueryAllSupportedHealthChecks`

Matched by name (the KB has no test IDs), so treat the counts as approximate.

| | Count |
|---|---|
| Health checks listed live (distinct test IDs) | {len(api_hc)} ({len({h["testId"] for h in api_hc})}) |
| Entries in the KB index | {len(kbh)} |
| Distinct test IDs with a matching KB entry | {len(matched_ids)} |
| Distinct test IDs with no KB entry found | {len({h["testId"] for h in hc_api_only})} |
| Live checks whose name is an untranslated message key | {sum(1 for h in api_hc if h["testName"].startswith("com.vmware."))} |
| KB entries with no live check (deprecated, removed, or general articles) | {len(hc_kb_only)} |

<details><summary>Live checks with no KB entry found ({len(hc_api_only)})</summary>

| Group | Test ID | Test name |
|---|---|---|""")
for h in sorted(hc_api_only, key=lambda h: (h["groupName"] or "", h["testId"])):
    L.append(f"| {esc(h['groupName'])} | `{h['testId']}` | {esc(h['testName'])} |")
L.append(f"\n</details>\n\n<details><summary>KB entries with no live check ({len(hc_kb_only)})</summary>\n\n| KB group | Entry | Version note |\n|---|---|---|")
for i in hc_kb_only:
    L.append(f"| {esc(i['group'])} | [{esc(i['key'])}]({i['url']}) | {esc(i['version'])} |")
L.append("\n</details>\n\n<details><summary>Matched checks</summary>\n\n| Test ID | Live name | KB entry | Match |\n|---|---|---|---|")
for h, i, sc, how in sorted(hc_match, key=lambda x: x[0]["testId"]):
    L.append(f"| `{h['testId']}` | {esc(h['testName'])} | [{esc(i['key'])}]({i['url']}) | {how} {sc:.2f} |")
L.append("\n</details>")

L.append("""
## 3. Capacity: VCF 9.1 vSAN capacity pages vs `VsanQuerySpaceUsage`

The documentation describes capacity by its UI label; the API by field. The mapping below is by meaning and was not
checked against live values (no vSAN cluster in the lab).

| Documented term | API field | Field exists in schema |
|---|---|---|""")
for s in docs:
    if s["kind"] == "manual" and s["items"]:
        for i in s["items"]:
            term = i["group"] or i["key"]
            sub = i["key"]
            if term.lower() == "system usage":
                f = "spaceDetail.spaceUsageByObjectType[] (system object types)"
            elif term in ("VM (user objects) usage", "Non-VM (user objects) usage", "Container volume snapshots",
                          "VMDK snapshots", "vSAN file share snapshots", "Current data"):
                f = "spaceDetail.spaceUsageByObjectType[] (per object type)"
            else:
                f = CAP.get(term, "")
            if sub and len(sub) < 60:
                term = f"{term}: {sub}"
            ok = "yes" if f and f.split(" ")[0] in space_fields else ("partly" if f else "no field; derived or UI-only")
            L.append(f"| {esc(term)} ({ref(s)}) | {('`' + f + '`') if f else ''} | {ok} |")

L.append("""
## 4. VCF Operations reference vs the vSAN API

VCF Operations publishes its own metric keys (for example `vSAN|Disk Space|Disk Space Used (%)`) without the vSAN API
field behind each one, so a row-by-row match is not possible. Coverage by object type:

| Object type | VCF Operations metrics | VCF Operations properties | API metrics | API properties |
|---|---|---|---|---|""")
api_m = collections.Counter(r.split("|")[1].strip() for r in open(os.path.join(ROOT, "metrics-api.md"), encoding="utf-8") if r.startswith("| ") and "| PERF |" in r or "| VSAN |" in r or "| VCPERF |" in r)
api_p = collections.Counter(r.split("|")[1].strip() for r in open(os.path.join(ROOT, "properties-api.md"), encoding="utf-8") if "| VSAN |" in r)
ops_m = collections.Counter(ops_type(s["title"]) for s in docs if s["kind"] == "ops-metric" for _ in s["items"])
ops_p = collections.Counter(ops_type(s["title"]) for s in docs if s["kind"] == "ops-property" for _ in s["items"])
for t in TYPES:
    L.append(f"| {t} | {ops_m.get(t, 0)} | {ops_p.get(t, 0)} | {api_m.get(t, 0)} | {api_p.get(t, 0)} |")
L.append("\n## Sources\n\n" + SRC_LIST)
open(os.path.join(ROOT, "comparison.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

print("perf: api", len(api_perf), "kb", len(kb_set), "matched", len(matched), "kb_only", len(kb_only), "api_only", len(api_only))
print("health: api", len(api_hc), "kb", len(kbh), "matched", len(hc_match), "api_only", len(hc_api_only), "kb_only", len(hc_kb_only))
print("docs rows: metrics", sum(map(len, mrows.values())), "properties", sum(map(len, prows.values())))
