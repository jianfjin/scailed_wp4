#!/usr/bin/env python3
"""Build the offline DDD design reader from the confirmed Markdown sources.

Requires Python-Markdown. Build the companion Archify diagram first, then run:
    python3 scripts/build_scailed_ddd_html.py
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "19_scailed_ddd_design.html"
BASELINE = DOCS / "domain-modeling/2026-11-26-pathfinder-semantic-baseline.md"
GLOSSARY = DOCS / "domain-modeling/pathfinder-boundaries/CONTEXT.md"
SESSION = DOCS / "domain-modeling/2026-11-26-cross-wp-ddd.md"
MAP = DOCS / "19_scailed_ddd_context_map.html"
SPEC = DOCS / "19_scailed_ddd_context_map.architecture.json"
DELIVERY = DOCS / "runbooks/pathfinder-semantic-cutover.md"
ADRS = [DOCS / "adr" / name for name in (
    "0004-source-wps-retain-content-authority.md",
    "0005-v1-independent-assessment-sessions.md",
    "0006-type-capabilities-remain-reference-information.md",
    "0007-withdrawn-inputs-stop-new-recommendations.md",
)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def render(text: str, source: Path) -> str:
    result = markdown.markdown(text, extensions=["tables", "fenced_code"])
    routes = {BASELINE: "implementation", GLOSSARY: "language", SESSION: "decisions",
              ROOT / "CONTEXT-MAP.md": "overview"}
    routes.update({p: "decisions" for p in ADRS})

    def link(match: re.Match) -> str:
        href = html.unescape(match.group(1))
        if href.startswith(("https:", "http:", "#")):
            return match.group(0)
        target = (source.parent / href.split("#", 1)[0]).resolve()
        if target in routes:
            return f'href="#{routes[target]}" data-route="{routes[target]}"'
        relative = os.path.relpath(target, OUT.parent)
        return f'href="{html.escape(relative, quote=True)}"'

    result = re.sub(r'href="([^"]+)"', link, result)
    return re.sub(r"(<table>.*?</table>)", r'<div class="table-wrap" tabindex="0">\1</div>', result, flags=re.S)


def parse_terms(text: str) -> list[dict]:
    group = "责任与交界"
    terms = []
    for section in re.split(r"(?m)^(## .+)$", text):
        if section.startswith("## "):
            group = section[3:].strip()
            if group == "Language":
                group = "责任与交界"
            continue
        for match in re.finditer(r"(?m)^\*\*(.+?)\*\*：\n(.*?)(?=^\*\*|\Z)", section, re.S):
            name, body = match.groups()
            chunks = re.split(r"(?m)^_Avoid_：", body.strip(), maxsplit=1)
            definition = chunks[0].strip()
            avoid = chunks[1].strip() if len(chunks) == 2 else ""
            terms.append({"name": name, "group": group, "definition": definition, "avoid": avoid,
                          "html": render(definition, GLOSSARY)})
    return terms


def section(text: str, title: str) -> str:
    match = re.search(rf"(?m)^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S)
    if not match:
        raise ValueError(f"Missing confirmed section: {title}")
    return match.group(1).strip()


def main() -> None:
    baseline = BASELINE.read_text()
    glossary = GLOSSARY.read_text()
    if "基线已确认" not in baseline or not MAP.exists():
        raise ValueError("A confirmed baseline and delivered diagram are required")
    terms = parse_terms(glossary)
    if len(terms) < 20:
        raise ValueError("Glossary extraction is incomplete")
    adrs = []
    for path in ADRS:
        source = path.read_text()
        clean = re.sub(r"\A---\n.*?\n---\n", "", source, flags=re.S).strip()
        title = re.search(r"(?m)^# (.+)$", clean).group(1)
        adrs.append({"id": path.name[:4], "title": title, "html": render(clean, path), "markdown": source})
    sources = [BASELINE, GLOSSARY, SESSION, ROOT / "CONTEXT-MAP.md", *ADRS, SPEC, MAP, DELIVERY]
    manifest = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in sources]
    data = {
        "date": "2026-11-27", "termCount": len(terms), "terms": terms, "adrs": adrs,
        "baselineHtml": render(baseline, BASELINE), "baselineMarkdown": baseline,
        "glossaryMarkdown": glossary, "sessionMarkdown": SESSION.read_text(),
        "decisionsHtml": render(section(baseline, "已确认的共同语言与业务约束"), BASELINE),
        "gapsHtml": render(DELIVERY.read_text(), DELIVERY) + "<details><summary>2026-11-26 原始设计差异记录（历史）</summary>" + render(section(baseline, "已有实现基础与差异"), BASELINE) + "</details>",
        "nextHtml": render("## 生产切换仍待确认\n\n内部实现已完成；来源 WP 的 RFC、消费者就绪确认及受控生产迁移仍未执行。详见 [切换 runbook](runbooks/pathfinder-semantic-cutover.md) 与 [RFC](rfcs/pathfinder-semantic-v2.md)。", DOCS / "index.md"),
        "manifest": manifest,
    }
    result = TEMPLATE.replace("__DATA__", safe_json(data))
    result = result.replace("__MAP__", html.escape(MAP.read_text(), quote=True))
    OUT.write_text(result)
    receipt = {"output": str(OUT.relative_to(ROOT)), "bytes": OUT.stat().st_size,
               "sha256": sha(OUT), "terms": len(terms), "adrs": len(adrs), "sources": manifest}
    (DOCS / "19_scailed_ddd_design.build.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(f"Built {receipt['output']}: {len(terms)} terms, {len(adrs)} ADRs, {receipt['bytes']:,} bytes")


TEMPLATE = r'''<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="description" content="SCAILED Pathfinder 已确认的 DDD 语义治理设计：WP2、WP3、WP4、WP8 的共同语言、责任边界、评估证据与版本撤回。">
<title>SCAILED · Pathfinder DDD 设计</title>
<style>
:root{--bg:#f4f7fa;--panel:#fff;--soft:#f6f8fb;--ink:#172b3e;--muted:#526779;--line:#dce4ec;--brand:#087c78;--tint:#e6f5f1;--blue:#245ec5;--amber:#8d560b;--amber-bg:#fff3df;--good:#116d50;--shadow:0 12px 32px #19334c08;--radius:16px}
[data-theme=dark]{color-scheme:dark;--bg:#101a25;--panel:#172635;--soft:#1c2e40;--ink:#edf4fb;--muted:#b1c2d2;--line:#354a5e;--brand:#79dbca;--tint:#173e41;--blue:#9cc1ff;--amber:#f1c37b;--amber-bg:#3b3022;--good:#8ce0b8;--shadow:0 12px 32px #0002}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 Inter,"Noto Sans CJK SC","Microsoft YaHei",system-ui,sans-serif}button,input,select{font:inherit}button{cursor:pointer;color:inherit}button,a,input,select,summary{touch-action:manipulation}a{color:var(--blue);text-underline-offset:3px}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,[tabindex]:focus-visible{outline:3px solid var(--brand);outline-offset:4px}h1,h2,h3,p{margin-top:0}h1{font-size:clamp(27px,2.5vw,38px);line-height:1.3;letter-spacing:-.7px;margin-bottom:12px}h2{font-size:22px;line-height:1.4}h3{font-size:16px;line-height:1.5}p{margin-bottom:13px}svg{display:block}code{font:12px/1.6 ui-monospace,monospace;background:var(--tint);color:var(--ink);border-radius:4px;padding:2px 5px;overflow-wrap:anywhere}.skip{position:fixed;top:-100px;left:16px;padding:9px 16px;background:var(--panel);z-index:20}.skip:focus{top:10px}
.topbar{padding:17px 28px;background:var(--panel);border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:16px}.brand{display:flex;align-items:center;gap:12px}.mark{width:39px;height:39px;display:grid;place-items:center;border-radius:12px;background:#087c78;color:white;font:700 15px ui-monospace,monospace}.brand strong{display:block;font-size:16px;letter-spacing:1px}.brand small{font-size:11px;color:var(--muted)}.top-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.button{display:inline-flex;align-items:center;justify-content:center;gap:7px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:7px 12px;color:var(--ink);font-size:13px;text-decoration:none;min-height:38px}.button:hover{border-color:var(--brand);background:var(--tint)}.button.primary{color:#fff;background:#087c78;border-color:#087c78}.button.small{padding:5px 9px;font-size:12px}.layout{display:grid;grid-template-columns:216px minmax(0,1fr);min-height:calc(100vh - 78px)}aside{padding:27px 16px;background:var(--panel);border-right:1px solid var(--line)}.side-inner{position:sticky;top:24px}.nav-label{font:600 10px/1.5 ui-monospace,monospace;letter-spacing:1.6px;color:var(--muted);padding:0 12px 13px}.nav{display:grid;gap:7px}.nav button{display:flex;align-items:center;gap:12px;text-align:left;border:1px solid transparent;background:none;border-radius:10px;padding:10px 11px;font-size:14px;width:100%}.nav button .num{font:11px/1.8 ui-monospace,monospace;color:var(--muted)}.nav button[aria-current=page]{background:var(--tint);border-color:var(--line);color:var(--brand);font-weight:650}.side-note{margin:26px 9px 0;padding-top:19px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}.side-note strong{display:block;color:var(--ink);margin-bottom:6px}.scope-list{display:flex;flex-wrap:wrap;gap:5px;margin-top:13px}.scope-list span{font:11px ui-monospace,monospace;padding:4px 6px;border:1px solid var(--line);border-radius:5px}main{min-width:0;max-width:1660px;width:100%;margin:auto;padding:31px 34px 50px}.view[hidden]{display:none!important}.eyebrow{font:600 11px/1.6 ui-monospace,monospace;letter-spacing:1.2px;color:var(--brand);margin-bottom:9px}.lead{max-width:900px;color:var(--muted);font-size:15px;margin-bottom:16px}.intro{display:flex;justify-content:space-between;align-items:flex-start;gap:22px}.intro>div{min-width:0}.status{font-size:12px;white-space:nowrap;background:var(--tint);color:var(--good);border-radius:24px;padding:5px 11px;display:inline-flex;gap:6px;align-items:center}.status:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}.meta{display:flex;gap:9px;flex-wrap:wrap;margin:16px 0 24px}.metric{display:flex;gap:8px;align-items:baseline;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:7px 11px;font-size:12px;color:var(--muted)}.metric strong{color:var(--ink);font:700 19px ui-monospace,monospace}.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow)}.section-title{display:flex;justify-content:space-between;gap:15px;align-items:center;margin:23px 0 12px}.section-title h2{font-size:18px;margin:0}.hint{color:var(--muted);font-size:12px}.notice{border:1px solid var(--line);border-left:3px solid var(--brand);background:var(--panel);border-radius:0 9px 9px 0;padding:12px 16px;color:var(--muted);font-size:13px;margin:16px 0 23px}.notice.amber{border-left-color:var(--amber)}.notice strong{color:var(--ink)}.diagram{overflow:clip}.diagram iframe{display:block;border:0;width:100%;height:820px;background:var(--panel)}.diagram-caption{border-top:1px solid var(--line);padding:11px 17px;color:var(--muted);font-size:12px;display:flex;gap:12px;justify-content:space-between;align-items:center}.diagram-caption a{white-space:nowrap}.domain-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.domain-button{padding:17px;text-align:left}.domain-button[aria-pressed=true]{border-color:var(--brand);background:var(--tint)}.domain-button:hover{border-color:var(--brand)}.domain-button .wp{font:700 11px ui-monospace,monospace;color:var(--brand)}.domain-button strong{display:block;margin:7px 0 5px;font-size:15px}.domain-button small{display:block;color:var(--muted);font-size:12px}.domain-detail{padding:22px;margin-top:13px}.detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}.detail-grid h3{font-size:12px;color:var(--muted);margin-bottom:7px}.detail-grid p{font-size:14px;margin-bottom:0}.domain-title{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px}.domain-title h2{font-size:18px;margin:0}.pill{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:18px;padding:3px 9px;font-size:11px;white-space:nowrap;color:var(--muted)}.pill.amber{color:var(--amber);background:var(--amber-bg);border-color:transparent}.pill.good{color:var(--good);background:var(--tint);border-color:transparent}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}.padded{padding:21px}.padded h3{margin-bottom:9px}.padded p:last-child{margin-bottom:0}.muted{color:var(--muted)}.filters{padding:17px 19px;margin:22px 0 17px}.filter-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.filter-row+.filter-row{margin-top:12px}.filter-row label{font-size:12px;color:var(--muted)}input[type=search],select{color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:9px 12px;min-height:42px;max-width:100%}input[type=search]{flex:1;min-width:160px}.chip{border:1px solid var(--line);background:var(--panel);border-radius:20px;padding:5px 10px;font-size:12px;min-height:34px}.chip[aria-pressed=true]{color:var(--brand);background:var(--tint);border-color:var(--brand)}.terms-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}.term{padding:20px}.term h3{margin:7px 0 10px;font-size:15px}.term .definition{font-size:14px}.term .definition p{margin-bottom:8px}.term .avoid{padding-top:10px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}.empty{grid-column:1/-1;padding:35px;text-align:center;color:var(--muted)}.control-panel{padding:24px;margin:23px 0 16px}.control-panel label{display:block;font-size:13px;margin-bottom:8px;font-weight:600}.control-panel select{width:min(100%,590px)}.result-grid{display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:13px}.result-card{padding:21px;border-top:3px solid var(--brand)}.result-card h2{font-size:12px;color:var(--muted);font-weight:500;margin-bottom:13px}.result-card strong{display:block;font-size:20px;line-height:1.4;margin-bottom:11px}.result-card p{font-size:13px;color:var(--muted);margin:0}.example-line{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:17px 0;font-size:12px;color:var(--muted)}.example-line .arrow{color:var(--brand)}.key-list{padding-left:19px;margin:10px 0}.key-list li{margin:8px 0;font-size:14px}.scenario-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.scenario-summary .card{padding:15px 17px}.scenario-summary strong{display:block;font:700 27px ui-monospace,monospace;margin:4px 0}.scenario-summary span{font-size:12px;color:var(--muted)}.sets{display:grid;grid-template-columns:1fr 1fr;gap:16px}.input-set{padding:20px}.input-set.affected{border-color:var(--amber)}.set-title{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:16px}.set-title h2{font-size:17px;margin:0}.version-list{display:grid;gap:7px}.version{display:grid;grid-template-columns:55px 1fr auto;gap:9px;align-items:center;border:1px solid var(--line);background:var(--soft);padding:10px 11px;border-radius:8px;font-size:12px;min-width:0}.version strong{font:600 13px ui-monospace,monospace}.version .version-info{min-width:0;color:var(--muted)}.version .version-info small{display:block;font-size:11px}.version.withdrawn{border-color:var(--amber);background:var(--amber-bg)}.version.affected{border-style:dashed;border-color:var(--amber)}.history{margin:17px 0 0;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:13px}.history strong{color:var(--ink)}.adr-grid{display:grid;gap:12px;margin-top:18px}.adr{padding:0;overflow:clip}.adr summary{display:flex;gap:12px;align-items:center;cursor:pointer;padding:17px 20px;font-size:15px;list-style:none}.adr summary::-webkit-details-marker{display:none}.adr summary:after{content:"＋";margin-left:auto;color:var(--muted)}.adr[open] summary:after{content:"−"}.adr summary .adr-no{font:600 11px ui-monospace,monospace;color:var(--brand);white-space:nowrap}.adr summary strong{font-weight:600}.adr .adr-body{border-top:1px solid var(--line);padding:20px 24px}.adr .adr-body h1{font-size:22px}.adr .adr-body h2{font-size:17px}.prose{line-height:1.95;overflow-wrap:anywhere}.prose h1{font-size:29px;margin:0 0 22px}.prose h2{font-size:21px;margin:29px 0 15px}.prose h3{font-size:16px;margin:24px 0 12px}.prose p{margin:0 0 14px}.prose ul,.prose ol{padding-left:22px}.prose li{margin:6px 0}.table-wrap{overflow:auto;max-width:100%;margin:16px 0;border-radius:8px}.prose table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.8}.prose th,.prose td{border:1px solid var(--line);padding:11px 13px;text-align:left;vertical-align:top;min-width:120px}.prose th{background:var(--soft);font-weight:650}.prose code{font-size:11px}.prose pre{white-space:pre-wrap;background:var(--soft);padding:16px;border:1px solid var(--line);border-radius:8px}.prose pre code{padding:0;background:none}.prose .table-wrap:focus-visible{outline-offset:0}.source-manifest{padding:18px 22px;margin-top:17px}.source-manifest summary{cursor:pointer;font-size:13px;font-weight:600}.source-row{display:flex;flex-direction:column;gap:3px;padding:11px 0;border-bottom:1px solid var(--line);font-size:12px;overflow-wrap:anywhere}.source-row:last-child{border:0}.source-row code{font-size:10px;color:var(--muted);background:none;padding:0}.reader-footer{border-top:1px solid var(--line);margin-top:28px;padding-top:15px;font-size:11px;color:var(--muted);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.full-report{padding:24px 28px;margin-top:15px}.full-report>summary{cursor:pointer;font-size:15px;font-weight:600}.full-report[open]>summary{margin-bottom:25px}.toast{position:fixed;bottom:22px;right:24px;background:var(--ink);color:var(--panel);border-radius:8px;padding:10px 16px;font-size:12px;box-shadow:var(--shadow);z-index:30}.toast[hidden]{display:none}.print-context{display:none}
@media(min-width:1800px){main{padding:36px 42px 55px}.diagram iframe{height:900px}}
@media(max-width:1120px){.layout{grid-template-columns:185px minmax(0,1fr)}main{padding:26px 23px 40px}.domain-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.detail-grid{grid-template-columns:1fr 1fr}.detail-grid>div:last-child{grid-column:1/-1}.result-grid{grid-template-columns:1fr 1fr}.result-card:last-child{grid-column:1/-1}.scenario-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.version{grid-template-columns:46px 1fr}.version .pill{grid-column:2;justify-self:start}.diagram iframe{height:790px}}
@media(max-width:760px){.topbar{padding:14px 17px;align-items:flex-start}.brand small{display:none}.top-actions{justify-content:flex-end}.top-actions .download-label{display:none}.layout{display:block}aside{padding:12px 14px;border-right:0;border-bottom:1px solid var(--line)}.side-inner{position:static}.nav{grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.nav button{font-size:12px;gap:6px;padding:8px 6px}.nav-label,.side-note{display:none}main{padding:24px 17px 35px}.intro{display:block}.intro>.status{margin:0 0 10px}.intro .status{font-size:11px}.intro h1{font-size:28px}.lead{font-size:14px}.meta{gap:6px}.metric{font-size:11px;padding:6px 8px}.metric strong{font-size:16px}.terms-grid,.two-col,.sets{grid-template-columns:1fr}.result-grid{grid-template-columns:1fr}.result-card:last-child{grid-column:auto}.detail-grid{grid-template-columns:1fr}.detail-grid>div:last-child{grid-column:auto}.domain-button{padding:14px}.domain-button small{font-size:11px}.diagram iframe{height:760px}.diagram-caption{display:block}.diagram-caption a{display:inline-block;margin-top:6px}.section-title{align-items:flex-start}.scenario-summary .card{padding:12px 14px}.scenario-summary strong{font-size:24px}.version{grid-template-columns:48px 1fr auto}.version .pill{grid-column:auto}.adr summary{padding:15px 14px;flex-wrap:wrap;gap:8px}.adr summary strong{font-size:13px}.adr .adr-body{padding:17px}.full-report{padding:20px 17px}.prose table{font-size:12px}.reader-footer{font-size:10px}.topbar .button{padding:7px 9px}.control-panel{padding:19px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
@media print{body{background:#fff;color:#111;font-size:11pt}.topbar{padding:0 0 16px;background:none}.top-actions,aside,.filters,.button,.reader-footer,.toast,.diagram{display:none!important}.layout{display:block}main{padding:18px 0;max-width:none}.view[hidden]{display:block!important}.view{break-before:page}.view:first-child{break-before:auto}.card{box-shadow:none;break-inside:avoid}.terms-grid,.sets,.result-grid,.two-col{display:block}.card{margin-bottom:12px}.print-context{display:block}.adr-body{display:block!important}.adr summary:after{display:none}.prose .table-wrap{overflow:visible}.prose table{font-size:9pt}details>*{display:block!important}.full-report>summary{margin-bottom:18px}.notice{background:none}.version{background:none}.pill{white-space:normal}}
</style>
</head>
<body>
<a class="skip" href="#main-content">跳转到文档正文</a>
<header class="topbar">
 <div class="brand"><div class="mark" aria-hidden="true">DDD</div><div><strong>SCAILED</strong><small>Pathfinder · 设计与共同语言</small></div></div>
 <div class="top-actions"><button class="button" id="download-baseline"><span aria-hidden="true">↓</span><span class="download-label">下载</span>基线</button><button class="button" id="print-doc">打印</button><button class="button" id="theme-toggle" aria-label="切换到深色主题">深色</button></div>
</header>
<div class="layout">
<aside aria-label="文档导航"><div class="side-inner"><div class="nav-label">DESIGN READER / 19</div>
 <nav class="nav">
  <button data-page="overview" aria-current="page"><span class="num">01</span>设计总览</button>
  <button data-page="language"><span class="num">02</span>共同语言</button>
  <button data-page="capabilities"><span class="num">03</span>评估语义</button>
  <button data-page="withdrawal"><span class="num">04</span>撤回影响</button>
  <button data-page="decisions"><span class="num">05</span>共识与 ADR</button>
  <button data-page="implementation"><span class="num">06</span>实现与原文</button>
 </nav>
 <div class="side-note"><strong>本轮设计基线已确认</strong><p>DDD 用于共同语言、责任边界与业务不变量。现有架构为模块化单体。</p><p>本仓库共识与各 WP 正式签署分别记录。</p><div class="scope-list"><span>WP2</span><span>WP3</span><span>WP4</span><span>WP8</span></div></div>
</div></aside>
<main id="main-content" tabindex="-1">
<section class="view" id="view-overview" aria-labelledby="title-overview">
 <div class="intro"><div><div class="eyebrow">DOMAIN-DRIVEN DESIGN · 2026.11.26</div><h1 id="title-overview">让交界处的含义与责任一致</h1><p class="lead">Pathfinder 的 DDD 设计基线：来源 WP 确认内容含义，WP4 保持含义地适配与执行评估。把机构、类型、角色，及参考、自报、核验分别表达。</p></div><span class="status">设计共识已确认</span></div>
 <div class="meta"><div class="metric"><strong>4</strong>交界工作包</div><div class="metric"><strong>13</strong>次讨论确认</div><div class="metric"><strong id="term-count">—</strong>个规范术语</div><div class="metric"><strong>4</strong>份 ADR</div></div>
 <div class="section-title"><h2>语义协作主路径</h2><span class="hint">可缩放、搜索和查看关系</span></div>
 <div class="card diagram"><iframe id="context-frame" title="Pathfinder 跨 WP 语义协作图" srcdoc="__MAP__"></iframe><div class="diagram-caption"><span>图表示知识交付与评估关系。软件限界上下文的进一步划分属于后续设计。</span><a href="19_scailed_ddd_context_map.html" target="_blank" rel="noopener">独立打开图 ↗</a></div></div>
 <div class="notice"><strong>阅读状态：</strong>设计基线保持原文。三值求值、逐项证据和精确撤回已完成内部实现；自报仍未核验，生产切换仍待来源 WP / 消费者确认与受控迁移。详见「实现与原文」。</div>
 <div class="section-title"><h2>内容负责方与消费边界</h2><span class="hint">选择一个工作包查看职责</span></div>
 <div class="domain-grid" id="domain-grid"></div><div class="card domain-detail" id="domain-detail" role="region" aria-label="工作包责任详情"></div>
 <div class="print-context"><p>WP2 分类参考、WP3 路线图、WP8 规则知识进入 WP4 评估。内容解释权保留在各来源 WP，WP4 负责适配与执行。</p></div>
 <div class="two-col" style="margin-top:17px"><div class="card padded"><span class="pill good">普通内容交付</span><h3 style="margin-top:12px">内容确认 → 接入验收</h3><p class="muted">内容负责方确认本批内容，WP4 按既定语义和兼容约定验收。</p></div><div class="card padded"><span class="pill amber">交界约定变更</span><h3 style="margin-top:12px">受影响供需双方确认 RFC</h3><p class="muted">字段不变也可能改变业务含义。变更分类取决于真实语义与兼容影响。</p></div></div>
</section>
<section class="view" id="view-language" aria-labelledby="title-language" hidden>
 <div class="eyebrow">UBIQUITOUS LANGUAGE</div><h1 id="title-language">把相似的词，分成准确的概念</h1><p class="lead">以下定义来自已确认的交界词表。采购文档的项目中性称谓有单独的语言语境。</p>
 <div class="card filters"><div class="filter-row"><label for="term-search">搜索词表</label><input type="search" id="term-search" placeholder="例如：能力、机构、未知、核验" autocomplete="off"><button class="button small" id="clear-search">清空</button><span class="hint" id="term-results" aria-live="polite"></span></div><div class="filter-row" id="term-groups" aria-label="按术语分类筛选"></div></div>
 <div class="terms-grid" id="terms-grid"></div><div style="margin-top:18px"><button class="button" id="download-glossary">↓ 下载完整词表 Markdown</button></div>
</section>
<section class="view" id="view-capabilities" aria-labelledby="title-capabilities" hidden>
 <div class="eyebrow">FINDING × SOURCE × VERIFICATION</div><h1 id="title-capabilities">能力判断与证据性质分别表达</h1><p class="lead">WP2 的类型能力是参考信息。本次能力判断来自本次回答与相应证据；自报可以参与推演，但保留未核验性质。</p>
 <div class="notice"><strong>设计语义演示：</strong>选择一种输入，查看如何表达该项能力及其对相关路径的含义。这里不执行真实规则，也不替代整条路径的条件核对。</div>
 <div class="card control-panel"><label for="capability-input">关于「安全处理能力」，本次获得了什么信息？</label><select id="capability-input"><option value="unknown">未回答，也没有其他依据</option><option value="self_yes">用户自报具备，尚未核验</option><option value="self_no">用户明确自报不具备</option><option value="verified">已有核验依据（概念示例）</option></select><div class="example-line"><span>类型参考信息</span><span class="arrow" aria-hidden="true">≠</span><span>本次能力判断</span><span class="arrow" aria-hidden="true">≠</span><span>真实性核验</span></div></div>
 <div class="result-grid" id="capability-result" role="region" aria-label="能力语义结果" aria-live="polite"></div>
 <div class="two-col" style="margin-top:18px"><div class="card padded"><h3>同一家机构，角色可以随场景变化</h3><p class="muted">机构是具体主体，「生物技术 SME」是分类，提供数据或使用数据是场景角色。类型关联的角色不能单独证明某家机构在某个场景的实际身份。</p></div><div class="card padded"><h3>V1 使用独立评估会话</h3><p class="muted">每次会话记录参与者类型与目标场景，不建立机构档案或跨会话机构历史。相似答案不能用于认定两个会话属于同一家机构。</p></div></div>
 <div class="notice amber"><strong>实现对照：</strong><code>evidence-v2</code> 已使用三值求值、逐项 finding 与未核验来源；<code>confidence</code> 表示填写完整度。旧 profile 保留原含义。自动核验流程及核验主体不在本次实现范围。</div>
</section>
<section class="view" id="view-withdrawal" aria-labelledby="title-withdrawal" hidden>
 <div class="eyebrow">EXACT VERSION DEPENDENCIES</div><h1 id="title-withdrawal">撤回沿精确依赖传播</h1><p class="lead">被撤回版本停止用于生成新建议。直接或间接依赖它的输入组合暂停使用，其他已确认有效且无该依赖的组合继续使用。</p>
 <div class="notice"><strong>示例：</strong>T/R/Q/L 分别是分类、路线图、问卷和规则包的版本别名。两套输入组合均假设已验收；T2 替换 T1，但不运行依赖 T1，且仍被内容方确认有效。</div>
 <div class="card control-panel"><label for="withdraw-select">内容负责方明确撤回了哪个版本？</label><div class="filter-row"><select id="withdraw-select"><option value="none">没有撤回</option><option value="T1">T1 · 分类参考版本 1</option><option value="R1">R1 · 路线图版本 1</option><option value="Q1">Q1 · 问卷版本 1</option><option value="L1">L1 · 规则包版本 1</option><option value="T2">T2 · 分类参考版本 2</option></select><button class="button" id="reset-withdraw">重置示例</button></div></div>
 <div class="scenario-summary" id="withdraw-summary" aria-live="polite"></div><div class="sets" id="withdraw-sets" role="region" aria-label="撤回影响结果"></div>
 <div class="notice amber"><strong>三个区别：</strong>依赖受影响不等于下游内容也被宣布撤回；版本替换沿革不等于运行依赖；新批次验收失败不等于上一版内容被撤回。</div>
 <p class="hint">这是设计语义示例。运行时已实现带来源确认声明的撤回接入、精确依赖检查及历史有效性标识；确认材料由管理员人工核对，正式跨 WP 认可与生产切换仍待完成。</p>
</section>
<section class="view" id="view-decisions" aria-labelledby="title-decisions" hidden>
 <div class="intro"><div><div class="eyebrow">CONFIRMED DESIGN RECORD</div><h1 id="title-decisions">共同理解已落到决策记录</h1><p class="lead">13 次确认形成这套语义治理基线。四份 ADR 记录重要取舍，细节保留在讨论记录中。</p></div><span class="status">本仓库设计共识</span></div>
 <div class="notice">这里的接受状态代表本仓库设计讨论已确认。各 WP 的正式认可、签署人员、问卷评审与核验责任仍需分别落实。</div>
 <div class="card padded prose" id="decisions-summary"></div><div class="section-title"><h2>四份 ADR · 点击展开阅读</h2><button class="button small" id="download-session">↓ 下载讨论记录</button></div><div class="adr-grid" id="adrs"></div>
</section>
<section class="view" id="view-implementation" aria-labelledby="title-implementation" hidden>
 <div class="eyebrow">DESIGN BASELINE ≠ IMPLEMENTATION RECEIPT</div><h1 id="title-implementation">设计共识与当前实现分别核对</h1><p class="lead">项目已有模块化单体、确定性核心、版本化快照、依赖校验、原子激活和评估版本绑定。下面列出本次内部验收结果、受控迁移步骤与未满足的生产门槛；原始差异记录单独保留。</p>
 <div class="card padded prose" id="implementation-gaps"></div><div class="section-title"><h2>待工程细化与跨 WP 落实</h2><span class="pill amber">后续设计事项</span></div><div class="card padded prose" id="next-steps"></div>
 <details class="card full-report" id="full-baseline"><summary>阅读 2026-11-26 原始基线全文（历史记录）</summary><article class="prose" id="baseline-document"></article></details>
 <details class="card source-manifest"><summary>源文档与 SHA-256 · 可核对本页来源</summary><div id="source-manifest"></div><button class="button small" id="download-manifest">↓ 下载来源清单</button></details>
</section>
<footer class="reader-footer"><span>源于已确认的 DDD 基线、交界词表、上下文图及 ADR 0004–0007</span><span>2026-11-27 · 单文件离线阅读</span></footer>
</main></div>
<div class="toast" id="toast" role="status" hidden></div>
<script id="ddd-data" type="application/json">__DATA__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('ddd-data').textContent);
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const PAGES=['overview','language','capabilities','withdrawal','decisions','implementation'];
function route(page,scroll=true){if(!PAGES.includes(page))page='overview';$$('.view').forEach(el=>{el.hidden=el.id!=='view-'+page});$$('[data-page]').forEach(el=>{if(el.dataset.page===page)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')});if(location.hash!=='#'+page)history.replaceState(null,'','#'+page);document.title='SCAILED · '+$('#title-'+page).textContent;if(scroll)window.scrollTo({top:0,behavior:'instant'})}
$$('[data-page]').forEach(b=>b.addEventListener('click',()=>route(b.dataset.page)));
document.addEventListener('click',event=>{const a=event.target.closest('a[data-route]');if(a){event.preventDefault();route(a.dataset.route)}});
window.addEventListener('hashchange',()=>route(location.hash.slice(1)));
let savedTheme=null;try{savedTheme=localStorage.getItem('scailed-ddd-theme')}catch(e){}
function setTheme(theme){document.documentElement.dataset.theme=theme;$('#theme-toggle').textContent=theme==='dark'?'浅色':'深色';$('#theme-toggle').setAttribute('aria-label',theme==='dark'?'切换到浅色主题':'切换到深色主题');try{localStorage.setItem('scailed-ddd-theme',theme)}catch(e){}const frame=$('#context-frame');try{if(frame.contentDocument){frame.contentDocument.documentElement.setAttribute('data-theme',theme)}}catch(e){}}
setTheme(savedTheme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
$('#theme-toggle').addEventListener('click',()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
$('#context-frame').addEventListener('load',()=>{setTheme(document.documentElement.dataset.theme)});
function download(text,name,type='text/markdown;charset=utf-8'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('#download-baseline').addEventListener('click',()=>download(DATA.baselineMarkdown,'pathfinder-semantic-baseline.md'));
$('#download-glossary').addEventListener('click',()=>download(DATA.glossaryMarkdown,'pathfinder-boundary-glossary.md'));
$('#download-session').addEventListener('click',()=>download(DATA.sessionMarkdown,'cross-wp-ddd-session.md'));
$('#download-manifest').addEventListener('click',()=>download(JSON.stringify(DATA.manifest,null,2),'scailed-ddd-sources.json','application/json'));
$('#print-doc').addEventListener('click',()=>window.print());
const DOMAINS=[
 {id:'WP2',name:'分类参考知识',brief:'类型、场景与能力词汇',concepts:'参与者类型、场景、能力词汇、类型参考能力。',authority:'确认分类词汇等源内容的业务含义。类型特征不直接成为本次评估事实。',exchange:'通过 pf.taxonomy.v1 提供输入；既有方案接收 WP4 问卷草案与使用反馈。'},
 {id:'WP3',name:'路线图知识',brief:'节点、关系与前置条件',concepts:'路线图节点、节点间关系、前置条件和方法框架。',authority:'确认路线图内容的业务含义。内容变化与交界语义变化分别判断。',exchange:'通过 pf.roadmap.v1 提供输入；既有方案接收 WP4 的路线图使用反馈。'},
 {id:'WP8',name:'规则知识',brief:'规则、引用与适用条件',concepts:'项目规则、法规引用、适用条件与配套规则测试。',authority:'确认项目规则与引用的业务含义。规则的已核实性质不替代对本次能力自报的核验。',exchange:'通过 pf.rulebundle.v1 提供输入；既有方案接收 WP4 的规则使用反馈。'},
 {id:'WP4',name:'评估与导航',brief:'独立会话、判断与建议',concepts:'独立评估会话、本次能力判断、来源与核验状态、条件性方向。',authority:'保持源含义地适配与执行评估，协调交界分歧；源内容解释权由对应 WP 保留。',exchange:'消费分类、路线图与规则；既有方案发布问卷与反馈。问卷评审和正式签署分工继续落实。'}
];
$('#domain-grid').innerHTML=DOMAINS.map((d,i)=>`<button class="card domain-button" data-domain="${d.id}" aria-pressed="${i===0}"><span class="wp">${d.id}</span><strong>${d.name}</strong><small>${d.brief}</small></button>`).join('');
function selectDomain(id){const d=DOMAINS.find(x=>x.id===id);$$('[data-domain]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.domain===id)));$('#domain-detail').innerHTML=`<div class="domain-title"><h2>${d.id} · ${d.name}</h2><span class="pill good">已确认责任原则</span></div><div class="detail-grid"><div><h3>核心概念</h3><p>${d.concepts}</p></div><div><h3>责任边界</h3><p>${d.authority}</p></div><div><h3>既有交界方案</h3><p>${d.exchange}</p></div></div>`}
$$('[data-domain]').forEach(b=>b.addEventListener('click',()=>selectDomain(b.dataset.domain)));selectDomain('WP2');
$('#term-count').textContent=DATA.termCount;
let activeGroup='全部';const groups=['全部',...new Set(DATA.terms.map(t=>t.group))];
$('#term-groups').innerHTML=groups.map(g=>`<button class="chip" data-group="${esc(g)}" aria-pressed="${g===activeGroup}">${esc(g)}</button>`).join('');
function renderTerms(){const q=$('#term-search').value.trim().toLocaleLowerCase();const terms=DATA.terms.filter(t=>(activeGroup==='全部'||t.group===activeGroup)&&(!q||[t.name,t.definition,t.avoid].join(' ').toLocaleLowerCase().includes(q)));$('#term-results').textContent=`${terms.length} / ${DATA.termCount} 项`;
$('#terms-grid').innerHTML=terms.length?terms.map(t=>`<article class="card term"><span class="pill">${esc(t.group)}</span><h3>${esc(t.name)}</h3><div class="definition">${t.html}</div>${t.avoid?`<div class="avoid">避免混用：${esc(t.avoid)}</div>`:''}</article>`).join(''):'<div class="card empty">没有匹配的术语。可清空搜索或选择其他分类。</div>'}
$('#term-search').addEventListener('input',renderTerms);$('#clear-search').addEventListener('click',()=>{$('#term-search').value='';renderTerms();$('#term-search').focus()});$$('[data-group]').forEach(b=>b.addEventListener('click',()=>{activeGroup=b.dataset.group;$$('[data-group]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));renderTerms()}));renderTerms();
const CAPABILITIES={
 unknown:[['未知','本次未回答，也没有其他依据。不能直接解释为具备或明确不具备。'],['没有足够判断依据','类型参考信息不补成本次能力事实。'],['条件性方向与待补信息','可以展示候选方向，列出需要确认的能力；明确尚不能确认相关路径可执行。']],
 self_yes:[['自报具备','使用本次回答形成肯定声明，与没有回答的未知分别表达。'],['自报 · 未核验','允许保留来源后参与推演，不自动升级为已核验事实。'],['注明依据的推演','说明结论基于自报。该项能力自报成立，不代表整条路径全部条件已经满足。']],
 self_no:[['明确自报不具备','这是本次的明确否定声明，与未回答的未知分别表达。'],['自报 · 未核验','保留其自报来源，不把它描述成独立核验后的事实。'],['说明相关能力缺口','对依赖该能力的路径说明本次已声明的缺口；整份结果状态仍由完整条件决定。']],
 verified:[['该项能力有核验依据','这里只演示核验与能力判断分别表达的概念。'],['已核验 · 概念示例','具体核验主体、依据及流程仍需落实到后续设计。'],['继续核对其余必要条件','一项能力已核验，不代表整条路径或其他声明均已核验。']]
};
function renderCapability(){const values=CAPABILITIES[$('#capability-input').value];const labels=['本次能力判断','证据与核验性质','对相关路径的表达'];$('#capability-result').innerHTML=values.map((v,i)=>`<article class="card result-card"><h2>${labels[i]}</h2><strong>${v[0]}</strong><p>${v[1]}</p></article>`).join('')}
$('#capability-input').addEventListener('change',renderCapability);renderCapability();
const VERSIONS=[
 {id:'T1',wp:'WP2',name:'分类参考',deps:[]},{id:'R1',wp:'WP3',name:'路线图',deps:['T1']},{id:'Q1',wp:'WP4',name:'问卷',deps:['T1']},{id:'L1',wp:'WP8',name:'规则包',deps:['T1','R1']},
 {id:'T2',wp:'WP2',name:'分类参考',deps:[],supersedes:'T1'},{id:'R2',wp:'WP3',name:'路线图',deps:['T2']},{id:'Q2',wp:'WP4',name:'问卷',deps:['T2']},{id:'L2',wp:'WP8',name:'规则包',deps:['T2','R2']}
];
const SETS=[{id:'A',ids:['T1','R1','Q1','L1'],history:'H-A'},{id:'B',ids:['T2','R2','Q2','L2'],history:'H-B'}];
function affectedBy(root){const affected=new Set(root==='none'?[]:[root]);let changed=true;while(changed){changed=false;VERSIONS.forEach(v=>{if(!affected.has(v.id)&&v.deps.some(d=>affected.has(d))){affected.add(v.id);changed=true}})}return affected}
function renderWithdrawal(){const root=$('#withdraw-select').value,affected=affectedBy(root),blocked=SETS.filter(s=>s.ids.some(id=>affected.has(id))).length;const metrics=[[root==='none'?0:1,'明确撤回的版本'],[blocked,'暂停新推演的组合'],[SETS.length-blocked,'其他可用组合'],[2,'保留的历史评估']];
$('#withdraw-summary').innerHTML=metrics.map(([n,label])=>`<div class="card"><span>${label}</span><strong>${n}</strong></div>`).join('');
$('#withdraw-sets').innerHTML=SETS.map(s=>{const hit=s.ids.some(id=>affected.has(id));return `<article class="card input-set ${hit?'affected':''}" data-set="${s.id}" data-affected="${hit}"><div class="set-title"><h2>输入组合 ${s.id}</h2><span class="pill ${hit?'amber':'good'}">${hit?'暂停新推演':'可继续使用'}</span></div><div class="version-list">${s.ids.map(id=>{const v=VERSIONS.find(x=>x.id===id),status=id===root?'已撤回':affected.has(id)?'依赖受影响':'本例仍有效';return `<div class="version ${id===root?'withdrawn':affected.has(id)?'affected':''}" data-version="${id}" data-state="${id===root?'withdrawn':affected.has(id)?'affected':'valid'}"><strong>${id}</strong><div class="version-info">${v.wp} · ${v.name}<small>依赖：${v.deps.join('、')||'无'}${v.supersedes?' · 替换沿革：'+v.supersedes:''}</small></div><span class="pill ${affected.has(id)?'amber':''}">${status}</span></div>`}).join('')}</div><div class="history"><strong>历史评估 ${s.history} 保留</strong><br>${hit?'标明来源已撤回或依赖受影响，不再作为当前有效建议。':'本例输入未受本次撤回影响。'}<br>原输入版本与原结果继续可追溯。</div></article>`}).join('')}
$('#withdraw-select').addEventListener('change',renderWithdrawal);$('#reset-withdraw').addEventListener('click',()=>{$('#withdraw-select').value='none';renderWithdrawal()});renderWithdrawal();
$('#decisions-summary').innerHTML=DATA.decisionsHtml;
$('#adrs').innerHTML=DATA.adrs.map((a,i)=>`<details class="card adr" id="adr-${a.id}" ${i===0?'open':''}><summary><span class="adr-no">ADR ${a.id}</span><strong>${esc(a.title)}</strong><span class="pill good">已接受</span></summary><article class="adr-body prose">${a.html}</article></details>`).join('');
$('#implementation-gaps').innerHTML=DATA.gapsHtml;$('#next-steps').innerHTML=DATA.nextHtml;$('#baseline-document').innerHTML=DATA.baselineHtml;
$('#source-manifest').innerHTML=DATA.manifest.map(s=>`<div class="source-row"><span>${esc(s.path)}</span><code>${s.sha256}</code></div>`).join('');
route(location.hash.slice(1),false);
</script>
</body>
</html>'''


if __name__ == "__main__":
    main()
