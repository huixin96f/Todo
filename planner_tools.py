#!/usr/bin/env python3
"""Tooling for planner.html — validation and state dump.

    python3 planner_tools.py validate   # validate only   <- the edit-loop command
    python3 planner_tools.py state      # print current data state + code counters
    python3 planner_tools.py preview    # serve planner.html locally at :8899
    python3 planner_tools.py build      # legacy: build .build/planner-artifact.html

The `build` command is retained for reference only. Since the 2026-08-16 migration to
GitHub Pages (R10.1/R10.2), publishing is `git push` of `planner.html` itself; the
derived artifact-host shim is obsolete and gitignored.

Edit scripts import the two parser helpers from here:

    from planner_tools import grab, parse_js_array

Nothing else in the folder is generated. `planner.html` is the source of truth and the
only file to edit; BUILD_OUT below is disposable and rebuilt on every run.
"""
import json
import os
import re
import sys

SRC = "planner.html"
BUILD_OUT = ".build/planner-artifact.html"


# ─────────────────────────────── parsing ───────────────────────────────

def grab(html, name):
    m = re.search(r"const " + name + r" = (\[[\s\S]*?\]);", html)
    if not m:
        raise SystemExit("could not locate const %s" % name)
    return m.group(1)


def parse_js_array(src):
    """EVENTS/POOL are JSON.stringify output; LONGTERM is a JS object literal."""
    try:
        return json.loads(src)
    except json.JSONDecodeError:
        pass
    s = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', src)
    s = re.sub(r",(\s*[\]}])", r"\1", s)  # trailing commas
    return json.loads(s)


# ────────────────────────────── validation ─────────────────────────────
# R3.2. Both checks exist because of real breakages: missing trailing commas broke
# the file twice, and stale leftover blocks created duplicate entries twice.

def validate(html):
    ok = True
    arrays = {}
    for name in ("EVENTS", "POOL", "LONGTERM"):
        try:
            arrays[name] = parse_js_array(grab(html, name))
            print("%s syntax: OK" % name)
        except Exception as e:
            print("%s SYNTAX ERROR: %s" % (name, e))
            ok = False

    for name in ("EVENTS", "POOL"):
        if name not in arrays:
            continue
        codes = [x.get("code") for x in arrays[name]]
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        if dupes:
            print("%s DUPLICATES: %s" % (name, ", ".join(dupes)))
            ok = False
        else:
            print("%s duplicates: none" % name)

    events = arrays.get("EVENTS")
    pool = arrays.get("POOL")
    if events is not None and pool is not None:
        overlap = sorted({e.get("code") for e in events} & {e.get("code") for e in pool} - {None})
        if overlap:
            print("EVENTS/POOL CROSS DUPLICATES: %s" % ", ".join(overlap))
            ok = False
        else:
            print("EVENTS/POOL overlap: none")

    cat_prefix = {name: p for p, name in PREFIXES}
    code_re = re.compile(r"^[A-Z]\d+$")
    for name in ("EVENTS", "POOL"):
        if name not in arrays:
            continue
        bad = []
        for x in arrays[name]:
            c = x.get("code")
            if not c or not code_re.fullmatch(c):
                bad.append("%s(invalid)" % (c or "?"))
                continue
            want = cat_prefix.get(x.get("category"))
            if want and not c.startswith(want):
                bad.append("%s(%s)" % (c, x.get("category")))
        if bad:
            print("%s CODE/CATEGORY: %s" % (name, ", ".join(bad)))
            ok = False
        else:
            print("%s code/category: OK" % name)

    if events is not None:
        by_day = {}
        for e in events:
            if e.get("status") == "Pending":
                by_day.setdefault(e.get("date"), []).append(e.get("order"))
        order_bad = []
        for d, orders in sorted(by_day.items()):
            got = sorted(o if o is not None else 99 for o in orders)
            if got != list(range(len(orders))):
                order_bad.append("%s%s" % (d, got))
        if order_bad:
            print("PENDING ORDER: %s" % "; ".join(order_bad))
            ok = False
        else:
            print("pending orders: OK")
        no_doneat = [e.get("code") for e in events
                     if e.get("status") == "Done" and not e.get("doneAt")]
        if no_doneat:
            print("DONE MISSING doneAt: %s" % ", ".join(no_doneat))
            ok = False
        else:
            print("doneAt present: OK")

    print("\nAll checks passed." if ok else "\nFIX REQUIRED.")
    return ok


# ──────────────────────────────── build ────────────────────────────────
# R10.2/R10.3. planner.html is a complete HTML document, but the artifact host wraps
# whatever it is given in its own <!doctype>/<head>/<body> skeleton. Publishing it
# verbatim nests a second <head> inside a <body>; the parser drops it along with the
# viewport meta, and the calendar renders at desktop width on a phone.
#
# Dropping the head also drops <meta charset="UTF-8">, and a <meta> in the body is too
# late for the parser's encoding prescan — verified failure, CJK titles rendered as
# mojibake. So the output is escaped to pure ASCII and is correct under any charset.
# The escaping is region-specific: HTML entities are NOT decoded inside <script>/<style>.

PRELUDE = """/* -- artifact host shim (generated by planner_tools.py - do not hand-edit) -- */
:root{color-scheme:light}
html,body{margin:0;padding:0;background:#f0f2f8;-webkit-text-size-adjust:100%}
"""


def js_escape(s):
    """Non-ASCII -> \\uXXXX, with surrogate pairs for astral characters."""
    out = []
    for c in s:
        n = ord(c)
        if n < 128:
            out.append(c)
        elif n > 0xFFFF:
            n -= 0x10000
            out.append("\\u%04X\\u%04X" % (0xD800 + (n >> 10), 0xDC00 + (n & 0x3FF)))
        else:
            out.append("\\u%04X" % n)
    return "".join(out)


def html_escape(s):
    return "".join(c if ord(c) < 128 else "&#%d;" % ord(c) for c in s)


def css_escape(s):
    """Non-ASCII in the stylesheet only ever appears in /* comments */ (box-drawing
    rules). Transliterate those. Anything else — a content:"✓" say — must not be
    silently mangled, so fail loudly and let a human decide."""
    def strip_comment(m):
        return "".join(c if ord(c) < 128 else "-" for c in m.group(0))

    s = re.sub(r"/\*[\s\S]*?\*/", strip_comment, s)
    leftover = sorted({c for c in s if ord(c) > 127})
    if leftover:
        raise SystemExit(
            "non-ASCII outside CSS comments: %r — needs a real CSS escape "
            "(\\XXXX), not transliteration. Fix planner_tools.py." % "".join(leftover)
        )
    return s


def build(html):
    """Extraction only, never a redesign — R7.1 and R10.4 apply here in full."""
    style = re.search(r"<style>([\s\S]*?)</style>", html)
    body = re.search(r"<body>([\s\S]*)</body>", html)
    title = re.search(r"<title>([\s\S]*?)</title>", html)
    if not style or not body:
        raise SystemExit("could not locate <style> or <body> in %s" % SRC)

    # Re-root `body{...}` onto the wrapper. The lookbehind keeps it from matching
    # inside a compound selector such as `.card-body{`.
    css, n = re.subn(r"(?<![-\w.#])body\s*\{", "#planner-root{", style.group(1))
    if n != 2:
        raise SystemExit(
            "expected 2 `body{` rules to re-root, found %d — "
            "planner.html changed shape; check before publishing" % n
        )

    parts = re.split(r"(<script>[\s\S]*?</script>)", body.group(1).strip())
    escaped_body = "".join(
        "<script>" + js_escape(p[len("<script>"):-len("</script>")]) + "</script>"
        if p.startswith("<script>") else html_escape(p)
        for p in parts
    )

    out = "\n".join([
        "<title>%s</title>" % html_escape(title.group(1) if title else "Planner"),
        "<style>",
        css_escape(PRELUDE + css),
        "</style>",
        '<div id="planner-root">',
        escaped_body,
        "</div>",
        "",
    ])

    for tag in ("<!doctype", "<html", "<head", "<body"):
        if tag in out.lower():
            raise SystemExit("%s leaked into the build — would nest inside the host skeleton" % tag)
    if not out.isascii():
        raise SystemExit("build output is not pure ASCII — charset-independence lost")

    os.makedirs(os.path.dirname(BUILD_OUT), exist_ok=True)
    open(BUILD_OUT, "w", encoding="utf-8").write(out)
    print("Wrote %s (%d KB) - re-rooted %d body rules, output is pure ASCII."
          % (BUILD_OUT, len(out.encode()) // 1024, n))


# ──────────────────────────────── state ───────────────────────────────
# Orientation for a session starting cold. This is the authoritative snapshot —
# the rules file deliberately does NOT hardcode one, because it goes stale (R2.1).

# R5.1: retired codes are never reused and gaps are never filled, so the high-water
# mark has to include codes no longer present in the data.
RETIRED = {'F1', 'F3', 'P4', 'P7', 'P12', 'P42',
           'T16', 'T20', 'T25', 'T43', 'T89', 'T98', 'R1'}

PREFIXES = [('T', 'Task'), ('P', 'Personal'), ('F', 'Follow-up'), ('M', 'Meeting'),
            ('S', 'Site Visit'), ('C', 'Call'), ('R', 'Review')]


def state(html):
    events = parse_js_array(grab(html, 'EVENTS'))
    pool = parse_js_array(grab(html, 'POOL'))
    longterm = parse_js_array(grab(html, 'LONGTERM'))

    pend = [e for e in events if e['status'] == 'Pending']
    print("EVENTS %d (%d Pending / %d Done) | POOL %d | LONGTERM %d"
          % (len(events), len(pend), len(events) - len(pend), len(pool), len(longterm)))

    def show(day, items):
        print("\n%s" % day)
        for e in sorted([x for x in items if x['status'] == 'Pending'],
                        key=lambda x: x.get('order', 99)):
            print("  %2d  %-5s %s" % (e['order'], e['code'], e['title']))
        for e in sorted([x for x in items if x['status'] == 'Done'],
                        key=lambda x: x.get('doneAt', '')):
            print("   done %s  %-5s %s" % (e['doneAt'][-5:], e['code'], e['title']))

    days = sorted({e['date'] for e in pend})
    if days:
        show("EARLIEST PENDING DAY — %s (roll these forward first, R6.1)" % days[0],
             [e for e in events if e['date'] == days[0]])
        for d in days[1:]:
            show("SCHEDULED — %s" % d, [e for e in events if e['date'] == d and e['status'] == 'Pending'])
    else:
        print("\nNo pending dated items.")

    print("\nPOOL (To Schedule)")
    for e in pool:
        print("      %-5s %s" % (e['code'], e['title']))
    print("\nLONGTERM")
    for e in longterm:
        print("      %s" % e['title'])

    live = {e.get('code') for e in events + pool}
    print("\nNEXT CODE PER PREFIX (highest ever issued + 1; retired codes stay burned)")
    for p, name in PREFIXES:
        ns = [int(c[1:]) for c in live | RETIRED if c and re.fullmatch(p + r'\d+', c)]
        print("      %-10s %s%d" % (name, p, (max(ns) + 1) if ns else 1))
    stray = sorted(live & RETIRED)
    print("\nretired codes present in data: %s" % (", ".join(stray) if stray else "none (correct)"))


def preview(port=8899):
    """Serve planner.html locally for in-chat preview (browser panel).

    Mirrors the Workout Tracker `preview` convention (2026-08-16). The source
    file is a full HTML document with its own <head>, so it is served as-is —
    no host-mimicking skeleton needed, unlike the old artifact-host build.
    ThreadingHTTPServer: a hung browser connection (observed once on 2026-08-18,
    CLOSE_WAIT pile-up froze the single-threaded server) must not block the
    whole preview.
    """
    import http.server
    import socketserver

    root = os.path.dirname(os.path.abspath(SRC))

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), H) as httpd:
        httpd.daemon_threads = True
        print("preview at http://127.0.0.1:%d/planner.html (ctrl-c to stop)" % port)
        httpd.serve_forever()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd not in ("all", "validate", "build", "state", "preview"):
        raise SystemExit(__doc__)

    html = open(SRC, encoding="utf-8").read()

    if cmd == "state":
        state(html)
        return 0
    if cmd == "preview":
        preview(int(sys.argv[2]) if len(sys.argv) > 2 else 8899)
        return 0
    if cmd in ("all", "validate"):
        if not validate(html):
            return 1  # never build or publish from a file that failed validation
    if cmd in ("all", "build"):
        build(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
