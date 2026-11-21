#!/usr/bin/env python3
"""Build docs/18_pathfinder_swagger.html: a single-file Swagger UI over
docs/18_pathfinder_openapi.json (swagger-ui assets inlined, works offline).
Run after scripts/build_openapi.py:
  python scripts/build_swagger_ui.py [path-to-swagger-ui-bundle.js path-to-swagger-ui.css]
"""
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/18_pathfinder_openapi.json"
OUT = ROOT / "docs/18_pathfinder_swagger.html"
CACHE = pathlib.Path(__file__).resolve().parent / ".cache"


def assets():
    if len(sys.argv) >= 3:
        return pathlib.Path(sys.argv[1]).read_text(), pathlib.Path(sys.argv[2]).read_text()
    CACHE.mkdir(exist_ok=True)
    js_p, css_p = CACHE / "swagger-ui-bundle.js", CACHE / "swagger-ui.css"
    if not (js_p.exists() and css_p.exists()):
        ua = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/131.0"}
        for url, p in (("https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js", js_p),
                       ("https://unpkg.com/swagger-ui-dist@5/swagger-ui.css", css_p)):
            if not p.exists():
                req = urllib.request.Request(url, headers=ua)
                p.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return js_p.read_text(), css_p.read_text()


def main():
    js, css = assets()
    spec = json.loads(SPEC.read_text())
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SCAILED Pathfinder - Public Interface (OpenAPI/Swagger)</title>
<style>{css}
body{{margin:0;background:#fafafa}}
.topbar{{background:#1367eb;color:#fff;padding:14px 24px;font-family:system-ui}}
.topbar a{{color:#cfe3ff;margin-left:18px}}</style></head>
<body>
<div class="topbar"><strong>SCAILED Pathfinder - WP Boundary Contracts &amp; Service API</strong>
<span style="opacity:.85;margin-left:12px">generated from the live FastAPI app + contracts/ - do not edit by hand; rerun <code>python3 scripts/build_openapi.py &amp;&amp; python3 scripts/build_swagger_ui.py</code></span>
<a href="https://edmf.atlassian.net/wiki/spaces/S/pages/11370498">Protocol page (Confluence)</a>
<a href="https://github.com/jianfjin/scailed_wp4/tree/main/contracts">contracts/</a></div>
<div id="swagger-ui"></div>
<script>{js}</script>
<script>
const SPEC = {json.dumps(spec)};
window.ui = SwaggerUIBundle({{ spec: SPEC, dom_id: "#swagger-ui", deepLinking: true, tryItOutEnabled: true,
 presets: SwaggerUIBundle.presets.apis, layout: "BaseLayout", filter: true, docExpansion: "list" }});
</script></body></html>"""
    OUT.write_text(html)
    print(f"wrote {OUT.name} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
