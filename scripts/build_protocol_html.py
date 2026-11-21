#!/usr/bin/env python3
"""Regenerate docs/16_wp_boundary_data_protocol.html from the markdown source.
Reuses the CSS/masthead shell already present in the HTML (everything before
the first <section); re-renders all h2-level sections and the sticky TOC,
and embeds the complete JSON files from contracts/samples for offline reading.
Run:  python3 scripts/build_protocol_html.py"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs/16_wp_boundary_data_protocol.md"
HTML = ROOT / "docs/16_wp_boundary_data_protocol.html"
SAMPLES = ROOT / "contracts/samples"

SAMPLE_STYLE = """<style id="contract-samples-style">
section{scroll-margin-top:calc(var(--toc-height,128px) + 16px)}
.sample-index{padding:0;list-style:none;display:grid;gap:8px;margin:18px 0}
.sample-index a,.sample-jump{color:var(--clay-d);text-underline-offset:3px;overflow-wrap:anywhere}
.sample-index a{font-size:13px;font-family:var(--mono)}
.sample-jump{font-size:13px;display:inline-block;margin:3px 0 10px}
.sample-controls,.sample-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.sample-controls{margin:20px 0 12px}.sample-controls[hidden],.sample-actions[hidden]{display:none}
.sample-button{font:600 12px var(--sans);min-height:40px;padding:8px 13px;cursor:pointer;border:1px solid var(--g300);border-radius:7px;background:var(--paper);color:var(--g700)}
.sample-button:hover{border-color:var(--clay-d);color:var(--clay-d)}
.sample-button:focus-visible,.sample-card summary:focus-visible,.sample-index a:focus-visible,.sample-jump:focus-visible,.sample-card pre:focus-visible{outline:3px solid var(--clay-d);outline-offset:4px}
.sample-card{background:var(--paper);border:1px solid var(--g300);border-radius:12px;padding:22px;margin:18px 0;scroll-margin-top:calc(var(--toc-height,128px) + 16px);min-width:0}
.sample-card h3{margin:0 0 8px;font-size:17px}.sample-card .sample-file{font-size:12px;overflow-wrap:anywhere;margin-bottom:10px}
.sample-card .sample-meta{font-size:12px;color:var(--g700);overflow-wrap:anywhere;margin:5px 0}
.sample-card .sample-meta code{overflow-wrap:anywhere}
.sample-card details{margin-top:15px;border-top:1px solid var(--g200);padding-top:12px}
.sample-card summary{cursor:pointer;font-size:13px;font-weight:650;padding:6px 0;width:fit-content}
.sample-card pre{margin:12px 0 0;max-height:560px;overflow:auto;max-width:100%;font-size:12px}
.sample-card pre code{font-size:inherit;white-space:pre}
.sample-actions{margin:14px 0 0}.sample-status{font-size:12px;color:var(--g700);min-height:1.65em;overflow-wrap:anywhere}
.sample-count{font-size:12px;color:var(--g700)}
.protocol-table{max-width:100%;overflow-x:auto;margin:14px 0}.protocol-table table{margin:0}
.protocol-table:focus-visible{outline:3px solid var(--clay-d);outline-offset:3px}
@media(max-width:600px){:root{--toc-height:0px}nav.toc{position:static}table.meta-table{width:100%;table-layout:fixed}.meta-table td{padding-right:12px;overflow-wrap:anywhere}.meta-table td:first-child{width:110px;white-space:normal}.sample-card{padding:16px}.sample-card pre{padding:14px;max-height:440px}.sample-actions{gap:8px}.sample-status{flex-basis:100%}}
@media print{.sample-controls,.sample-actions{display:none!important}.sample-card{break-inside:auto}.sample-card details::details-content{content-visibility:visible}.sample-card details>pre{display:block;max-height:none;overflow:visible;white-space:pre-wrap}.sample-card pre code{white-space:pre-wrap;overflow-wrap:anywhere}}
</style>"""

SAMPLE_SCRIPT = """<script id="contract-samples-script">
(() => {
  const cards = [...document.querySelectorAll('.sample-card')];
  document.querySelectorAll('.sample-controls,.sample-actions').forEach(el => el.hidden = false);
  document.querySelectorAll('[data-samples-expand]').forEach(button => {
    button.addEventListener('click', () => {
      cards.forEach(card => card.querySelector('details').open = button.dataset.samplesExpand === 'true');
    });
  });
  async function copyText(text) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) { /* A file opened offline may need the selection-based fallback. */ }
    const previous = document.activeElement;
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.append(textarea);
    textarea.select();
    let copied = false;
    try { copied = document.execCommand('copy'); } catch (_) {}
    textarea.remove();
    previous?.focus({preventScroll:true});
    return copied;
  }
  cards.forEach(card => {
    const code = card.querySelector('[data-sample-code]');
    const status = card.querySelector('[role="status"]');
    card.querySelector('[data-copy-sample]').addEventListener('click', async () => {
      if (await copyText(code.textContent)) {
        status.textContent = 'Copied ' + card.dataset.filename;
      } else {
        card.querySelector('details').open = true;
        const range = document.createRange();
        range.selectNodeContents(code);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        code.parentElement.focus({preventScroll:true});
        status.textContent = 'Automatic copy unavailable. JSON selected; use your copy shortcut.';
      }
    });
    card.querySelector('[data-download-sample]').addEventListener('click', () => {
      const url = URL.createObjectURL(new Blob([code.textContent], {type:'application/json;charset=utf-8'}));
      const link = document.createElement('a');
      link.href = url;
      link.download = card.dataset.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  });
  function openLinkedSample() {
    const card = cards.find(card => '#' + card.id === location.hash);
    if (card) {
      card.querySelector('details').open = true;
      requestAnimationFrame(() => card.scrollIntoView({block:'start'}));
    }
  }
  window.addEventListener('hashchange', openLinkedSample);
  window.addEventListener('load', openLinkedSample);
  const toc = document.querySelector('nav.toc');
  function measureToc() {
    const height = getComputedStyle(toc).position === 'sticky' ? toc.getBoundingClientRect().height : 0;
    document.documentElement.style.setProperty('--toc-height', height + 'px');
  }
  measureToc();
  openLinkedSample();
  if ('ResizeObserver' in window) new ResizeObserver(measureToc).observe(toc);
  else window.addEventListener('resize', measureToc);
  let beforePrint;
  window.addEventListener('beforeprint', () => {
    beforePrint = cards.map(card => card.querySelector('details').open);
    cards.forEach(card => card.querySelector('details').open = true);
  });
  window.addEventListener('afterprint', () => {
    if (beforePrint) cards.forEach((card, index) => card.querySelector('details').open = beforePrint[index]);
  });
})();
</script>"""


def sample_anchor(path):
    return "sample-" + path.name.removesuffix(".snapshot.json")


def render_samples():
    contract_order = {
        "pf.taxonomy.v1": 0, "pf.roadmap.v1": 1, "pf.questionnaire.v1": 2,
        "pf.rulebundle.v1": 3, "pf.feedback.v1": 4,
    }
    titles = {
        "pf.taxonomy.v1": "Stakeholder taxonomy", "pf.roadmap.v1": "Roadmap",
        "pf.questionnaire.v1": "Questionnaire", "pf.rulebundle.v1": "Regulatory rule bundle",
        "pf.feedback.v1": "Aggregated feedback",
    }
    samples = []
    for path in SAMPLES.glob("*.json"):
        raw = path.read_bytes().decode("utf-8")
        samples.append((path, raw, json.loads(raw)))
    if not samples:
        raise ValueError(f"No JSON samples found in {SAMPLES}")
    samples.sort(key=lambda s: (contract_order[s[2]["contract"]], s[2]["payload"].get("recipient", ""), s[0].name))
    index, cards = [], []
    for i, (path, raw, doc) in enumerate(samples):
        contract, manifest = doc["contract"], doc["manifest"]
        recipient = doc["payload"].get("recipient")
        title = titles[contract] + (f" — to {recipient}" if recipient else "")
        anchor = sample_anchor(path)
        index.append(f'<li><a href="#{anchor}">{html.escape(path.name)}</a></li>')
        route = manifest["producer_wp"] + (f" → {recipient}" if recipient else "")
        cards.append(
            f'<article class="sample-card" id="{anchor}" data-filename="{html.escape(path.name)}">'
            f'<h3>{html.escape(title)}</h3>'
            f'<p class="sample-file"><code>{html.escape(path.name)}</code></p>'
            f'<p class="sample-meta"><strong>{html.escape(route)}</strong> · <code>{html.escape(contract)}</code></p>'
            f'<p class="sample-meta">Snapshot: <code>{html.escape(manifest["snapshot_id"])}</code></p>'
            '<div class="sample-actions" hidden>'
            f'<button type="button" class="sample-button" data-copy-sample aria-label="Copy {path.name}">Copy JSON</button>'
            f'<button type="button" class="sample-button" data-download-sample aria-label="Download {path.name}">Download JSON</button>'
            '<span class="sample-status" role="status" aria-live="polite"></span></div>'
            f'<details{" open" if i == 0 else ""}><summary>Show complete JSON · {len(raw.encode("utf-8")):,} bytes</summary>'
            f'<pre tabindex="0" aria-label="{path.name} JSON"><code class="language-json" data-sample-code>{html.escape(raw)}</code></pre>'
            '</details></article>'
        )
    controls = (
        '<div class="sample-controls" hidden>'
        '<button type="button" class="sample-button" data-samples-expand="true">Expand all JSON</button>'
        '<button type="button" class="sample-button" data-samples-expand="false">Collapse all JSON</button>'
        f'<span class="sample-count">{len(samples)} complete snapshot files</span></div>'
    )
    return '<ul class="sample-index">' + ''.join(index) + '</ul>' + controls + ''.join(cards)

def slug(t):
    return re.sub(r"[^a-z0-9 -]", "", t.lower()).replace(" ", "-")

def convert(md_text):
    # markdown lib via the project venv if available, else system python
    py = subprocess.run([sys.executable, "-c", "import markdown"], capture_output=True)
    exe = sys.executable if py.returncode == 0 else "python3"
    r = subprocess.run(
        [exe, "-c",
         "import markdown,sys; print(markdown.markdown(sys.stdin.read(), "
         "extensions=['tables','fenced_code','attr_list']))"],
        input=md_text, capture_output=True, text=True)
    if r.returncode:
        sys.exit("markdown conversion failed: " + r.stderr)
    return r.stdout

md = MD.read_text()
if md.count("<!-- CONTRACT_SAMPLES -->") != 1:
    sys.exit("Expected exactly one CONTRACT_SAMPLES marker in the Markdown source")
sample_html = render_samples()
# split off front matter (h1 + metadata table) — the shell's masthead carries it
body_md = re.sub(r"^# .*?\n", "", md, count=1, flags=re.M)
body_md = re.sub(r"^\| \| \|\n(?:\|.*\|\n)+\n?", "", body_md)
sections = re.split(r"^## ", body_md, flags=re.M)[1:]

old = HTML.read_text()
shell = old.split("<section", 1)[0]          # head + css + masthead + up to first section
tail = old.rsplit("</section>", 1)[-1]       # closing tags / footer
shell = re.sub(r'<style id="contract-samples-style">.*?</style>', '', shell, flags=re.S)
shell = shell.replace('</head>', SAMPLE_STYLE + '</head>')
tail = re.sub(r'<script id="contract-samples-script">.*?</script>', '', tail, flags=re.S)
tail = re.sub(r'Generated \d{4}-\d{2}-\d{2} · source: ', 'Generated from: ', tail)
tail = tail.replace('</body>', SAMPLE_SCRIPT + '</body>')

parts, navs = [], []
for i, sec in enumerate(sections, 1):
    lines = sec.splitlines()
    title = lines[0].strip()
    anchor = f"{i}-" + slug(re.sub(r"^\d+\.\s*", "", title))
    inner = convert("\n".join(lines[1:]).strip() + "\n")
    inner = re.sub(
        r'(<table>.*?</table>)',
        r'<div class="protocol-table" tabindex="0" role="region" aria-label="Protocol table; scroll horizontally if needed">\1</div>',
        inner, flags=re.S,
    )
    inner = inner.replace("<!-- CONTRACT_SAMPLES -->", sample_html)
    if i == 5:
        for subsection, sample_id in (
            (1, "sample-wp2-taxonomy"), (2, "sample-wp3-roadmap"),
            (3, "sample-wp4-questionnaire"), (4, "sample-wp8-rulebundle"),
            (5, "sample-wp4-feedback-wp2"),
        ):
            inner = re.sub(
                rf'(<h3>5\.{subsection}\s.*?</h3>)',
                rf'\1\n<a class="sample-jump" href="#{sample_id}">View complete JSON sample{("s (WP2 / WP3 / WP8)" if subsection == 5 else "")}</a>',
                inner, count=1,
            )
    navs.append(f'<a href="#{anchor}"><b>{i:02d}</b> {title}</a>')
    parts.append(f'<section id="{anchor}"><div class="sec-head"><span class="idx">{i:02d}</span>'
                 f'<h2>{title}</h2></div>\n{inner}</section>')

# rebuild nav line inside the shell, replace sections
new_nav = '<nav class="toc">' + "".join(navs) + "</nav>"
shell = re.sub(r'<nav class="toc">.*?</nav>', new_nav, shell, flags=re.S)
out = shell.rstrip() + "\n" + "".join(parts) + tail
HTML.write_text(out)
print(f"wrote {HTML.name}: {len(sections)} sections, {len(out)//1024} KB")
