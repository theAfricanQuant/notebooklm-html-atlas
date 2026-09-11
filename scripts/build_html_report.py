#!/usr/bin/env python3
"""Create a portable HTML evidence report from NotebookLM JSON exports."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


TYPE_NAMES = {
    "SourceType.YOUTUBE": "YouTube", "SourceType.WEB_PAGE": "Web page",
    "SourceType.PDF": "PDF", "SourceType.TEXT": "Text",
    "SourceType.GOOGLE_DOCS": "Google Doc", "SourceType.GOOGLE_SLIDES": "Google Slides",
}


def e(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def anchor(source_id: object) -> str:
    return "source-" + hashlib.sha1(str(source_id).encode()).hexdigest()[:10]


def source_type(source: dict) -> str:
    return TYPE_NAMES.get(source.get("type"), str(source.get("type") or "Source").replace("SourceType.", "").title())


def unique_citations(qa: dict) -> list[dict]:
    output, seen = [], set()
    for ref in qa.get("references", []):
        key = str(ref.get("cited_text") or "")[:100]
        if key and key not in seen:
            seen.add(key)
            output.append(ref)
    return output


def numbers(specification: str) -> list[int]:
    output = []
    for part in specification.split(","):
        try:
            if "-" in part:
                start, end = map(int, part.split("-", 1))
                output.extend(range(start, end + 1))
            else:
                output.append(int(part.strip()))
        except ValueError:
            continue
    return output


def citation_tokens(answer: str, refs: list[dict], source_map: dict[str, dict]) -> tuple[str, dict[str, str]]:
    """Replace NotebookLM citation markers with safe placeholders before parsing Markdown."""
    tokens: dict[str, str] = {}

    def citation(match: re.Match) -> str:
        links = []
        for number in numbers(match.group(1)):
            if not 1 <= number <= len(refs):
                continue
            source = source_map.get(str(refs[number - 1].get("source_id")))
            if source:
                link = f'<a class="cite" href="#{anchor(source["id"])}">{e(source.get("title") or "Untitled")}</a>'
                if link not in links:
                    links.append(link)
        if not links:
            return match.group(0)
        token = f"CITETOKEN{len(tokens)}ENDCITE"
        tokens[token] = '<span class="cites">' + ', '.join(links) + '</span>'
        return token

    return re.sub(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]", citation, answer), tokens


def inline_html(text: str, tokens: dict[str, str]) -> str:
    """Escape prose and apply a deliberately small, predictable Markdown subset."""
    output = e(text)
    for token, markup in tokens.items():
        output = output.replace(token, markup)
    output = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", output)
    output = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", output)
    output = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", output)
    return output


def wrap_label(label: str, width: int = 48) -> list[str]:
    words, lines, current = label.split(), [], []
    for word in words:
        proposal = ' '.join(current + [word])
        if current and len(proposal) > width:
            lines.append(' '.join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(' '.join(current))
    return lines


def causal_svg(code_lines: list[str]) -> str | None:
    """Turn NotebookLM's exported bracket-and-arrow causal chain into native SVG."""
    labels = []
    for line in code_lines:
        match = re.match(r'^\s*\[(.+)\]\s*$', line)
        if match:
            labels.append(match.group(1).replace('──►', '→'))
    if not (3 <= len(labels) <= 8 and any('▼' in line or '│' in line for line in code_lines)):
        return None

    x, width, top, gap = 66, 788, 58, 46
    cards = []
    y = top
    for index, label in enumerate(labels):
        lines = wrap_label(label)
        height = 54 + len(lines) * 23
        cards.append((index, label, lines, y, height))
        y += height + gap
    height = y - gap + 34
    markup = [
        f'<figure class="causal-map"><figcaption><span>Causal cascade</span><strong>How the source connects its claims</strong></figcaption>',
        f'<svg viewBox="0 0 920 {height}" role="img" aria-label="Causal relationships among key claims">',
        '<defs><marker id="causal-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z"/></marker></defs>',
    ]
    for index, label, lines, card_y, card_height in cards:
        if index:
            previous = cards[index - 1]
            start_y = previous[3] + previous[4]
            end_y = card_y
            markup.append(f'<path class="causal-link" d="M460 {start_y + 7} V{end_y - 12}" marker-end="url(#causal-arrow)"/>')
        markup.append(f'<g class="causal-node causal-node-{index % 5}"><rect x="{x}" y="{card_y}" width="{width}" height="{card_height}" rx="12"/><text x="{x + 27}" y="{card_y + 30}" class="causal-step">{index + 1:02}</text>')
        text_y = card_y + 37
        for line_index, line in enumerate(lines):
            markup.append(f'<text x="{x + 76}" y="{text_y + line_index * 23}" class="causal-label">{e(line)}</text>')
        markup.append('</g>')
    markup.append('</svg></figure>')
    return ''.join(markup)

def markdown_html(answer: str, refs: list[dict], source_map: dict[str, dict]) -> str:
    """Render a safe Markdown subset as semantic HTML without adding dependencies."""
    text, tokens = citation_tokens(answer, refs, source_map)
    result: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_kind: str | None = None
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            result.append('<p>' + inline_html(' '.join(paragraph), tokens) + '</p>')
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items, list_kind
        if list_items and list_kind:
            result.append(f'<{list_kind}>' + ''.join(f'<li>{inline_html(item, tokens)}</li>' for item in list_items) + f'</{list_kind}>')
            list_items, list_kind = [], None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith('```'):
            flush_paragraph()
            flush_list()
            if in_code:
                chart = causal_svg(code_lines)
                result.append(chart if chart else '<pre><code>' + e('\n'.join(code_lines)) + '</code></pre>')
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(raw_line)
            continue
        heading = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', line)
        bullet = re.match(r'^\s*[-+*]\s+(.+)$', line)
        ordered = re.match(r'^\s*\d+[.)]\s+(.+)$', line)
        if heading:
            flush_paragraph()
            flush_list()
            level = min(6, max(2, len(heading.group(1)) + 1))
            result.append(f'<h{level}>' + inline_html(heading.group(2), tokens) + f'</h{level}>')
        elif re.match(r'^\s{0,3}([-*_])(?:\s*\1){2,}\s*$', line):
            flush_paragraph()
            flush_list()
            result.append('<hr>')
        elif bullet or ordered:
            flush_paragraph()
            kind, content = ('ul', bullet.group(1)) if bullet else ('ol', ordered.group(1))
            if list_kind and list_kind != kind:
                flush_list()
            list_kind = kind
            list_items.append(content)
        elif not line.strip():
            flush_paragraph()
            flush_list()
        else:
            paragraph.append(line.strip())
    if in_code:
        chart = causal_svg(code_lines)
        result.append(chart if chart else '<pre><code>' + e('\n'.join(code_lines)) + '</code></pre>')
    flush_paragraph()
    flush_list()
    return ''.join(result) or '<p>No answer supplied.</p>'

def flow(source_count: int, questions: int, excerpts: int) -> str:
    blocks = [("NOTEBOOKLM", "Source export", f"{source_count} sources"), ("NOTEBOOKLM", "Q&A export", f"{questions} questions"), ("LOCAL", "Citation map", f"{excerpts} source references"), ("OUTPUT", "HTML atlas", "1 portable page")]
    markup = ['<svg viewBox="0 0 920 205" class="flow" role="img" aria-label="NotebookLM exports become a local citation-linked HTML report"><defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z"/></marker></defs>']
    for index, (eyebrow, label, metric) in enumerate(blocks):
        x = 20 + index * 230
        if index:
            markup.append(f'<path class="arrow" d="M{x - 70} 103H{x}"/>')
        markup.append(f'<g><rect x="{x}" y="40" width="150" height="125"/><text x="{x + 18}" y="73" class="eyebrow">{eyebrow}</text><text x="{x + 18}" y="105" class="flow-label">{label}</text><text x="{x + 18}" y="139" class="flow-metric">{metric}</text></g>')
    return "".join(markup) + "</svg>"


def render(title: str, sources_file: dict, qas: list[dict]) -> str:
    sources = [item for item in sources_file.get("sources", []) if item.get("id") and str(item.get("title") or "").strip()]
    source_map = {str(item["id"]): item for item in sources}
    citations = [unique_citations(qa) for qa in qas]
    excerpts: dict[str, list[str]] = defaultdict(list)
    for refs in citations:
        for ref in refs:
            text, source_id = str(ref.get("cited_text") or "").strip(), str(ref.get("source_id") or "")
            if text and source_id in source_map and text not in excerpts[source_id]:
                excerpts[source_id].append(text)
    counts = Counter(source_type(source) for source in sources)
    ceiling = max(counts.values(), default=1)
    bars = "".join(f'<div class="bar"><span>{e(kind)}</span><i><b style="width:{count / ceiling * 100:.0f}%"></b></i><strong>{count}</strong></div>' for kind, count in counts.most_common())
    qa_markup = []
    for index, (qa, refs) in enumerate(zip(qas, citations), 1):
        cited = sorted({str(ref.get("source_id")) for ref in refs if str(ref.get("source_id")) in source_map})
        links = "".join(f'<li><a href="#{anchor(source_map[item]["id"])}">{e(source_map[item].get("title"))}</a></li>' for item in cited)
        qa_markup.append(f'<article class="qa"><div class="qnum">Q{index:02}</div><div><p class="question">{e(qa.get("question") or f"NotebookLM question {index}")}</p><div class="answer">{markdown_html(str(qa.get("answer") or "No answer supplied."), refs, source_map)}</div><details><summary>{len(cited)} cited source(s)</summary><ul>{links or "<li>No granular citations supplied</li>"}</ul></details></div></article>')
    source_markup = []
    for source in sources:
        source_id, url = str(source["id"]), str(source.get("url") or "")
        original = f'<a class="source-link" href="{e(url)}" target="_blank" rel="noreferrer">Open source <span aria-hidden="true">↗</span></a>' if url.startswith(("https://", "http://")) else '<span class="source-unavailable">Original URL unavailable</span>'
        source_markup.append(f'<article id="{anchor(source_id)}" class="source"><div class="meta">{e(source_type(source))} · {e(str(source.get("created_at") or "")[:10])}</div><h3>{e(source.get("title"))}</h3><footer>{original}</footer></article>')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>
:root{{--paper:#eaf0eb;--ink:#142c25;--pine:#19594c;--leaf:#5f9368;--line:#b6c8bc;--wash:#d7e4da;--soft:#4f665c;--signal:#e4ad29}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 Georgia,serif}}main{{max-width:1120px;margin:auto;padding:28px}}header{{padding:48px 0 30px;border-bottom:1px solid var(--line)}}.eyebrow,.meta,.qnum{{font:600 11px Arial,sans-serif;letter-spacing:.12em;color:var(--soft)}}h1{{max-width:760px;margin:14px 0 15px;font:500 clamp(2.8rem,8vw,6rem)/.88 Arial,sans-serif;letter-spacing:-.065em}}.lede{{max-width:660px;color:var(--soft);font-size:1.1rem}}h2{{margin:54px 0 16px;padding-bottom:10px;border-bottom:1px solid var(--line);font:500 1.9rem/1 Arial,sans-serif;letter-spacing:-.045em}}h3{{font:600 1.1rem/1.2 Arial,sans-serif;letter-spacing:-.025em}}a{{color:var(--pine);text-underline-offset:3px}}.flow{{display:block;width:100%;margin:31px 0 8px}}.flow rect{{fill:var(--wash);stroke:var(--line)}}.flow .arrow{{fill:none;stroke:var(--pine);stroke-width:1.5;marker-end:url(#arr)}}.flow #arr path{{fill:var(--pine)}}.flow .eyebrow{{font:600 11px Arial,sans-serif;letter-spacing:.1em;fill:var(--soft)}}.flow-label{{font:600 16px Arial,sans-serif;fill:var(--ink)}}.flow-metric{{font:600 18px Arial,sans-serif;fill:var(--pine)}}.split{{display:grid;grid-template-columns:1fr 1.5fr;gap:40px}}.bar{{display:grid;grid-template-columns:92px 1fr 20px;gap:9px;align-items:center;margin:11px 0;font:13px Arial,sans-serif}}.bar i{{height:8px;background:var(--wash)}}.bar b{{display:block;height:100%;background:var(--leaf)}}.notice{{align-self:start;padding:19px;border-left:3px solid var(--signal);background:color-mix(in srgb,var(--signal) 12%,transparent);color:var(--soft)}}.qa{{display:grid;grid-template-columns:52px 1fr;gap:17px;padding:22px 0;border-bottom:1px solid var(--line)}}.qa h3{{margin:0 0 9px}}.qa p{{max-width:780px;margin:0}}.cite{{display:inline-block;margin:0 2px;padding:1px 5px;background:var(--wash);font:12px Arial,sans-serif;text-decoration:none}}details{{margin-top:11px}}summary{{cursor:pointer;color:var(--pine);font:13px Arial,sans-serif}}details p,details ul{{margin:9px 0 0}}.sources{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}}.source{{padding:18px;background:#f8fbf8;border:1px solid var(--line)}}.source h3{{margin:12px 0 8px}}.source>p{{color:var(--soft);font-size:.93rem}}.source footer{{display:flex;justify-content:space-between;gap:8px;padding-top:11px;border-top:1px solid var(--line);font:11px Arial,sans-serif;color:var(--soft)}}body>main>footer{{margin-top:54px;padding:20px 0;border-top:1px solid var(--line);font:12px Arial,sans-serif;color:var(--soft)}}@media(max-width:720px){{main{{padding:18px}}.flow{{min-width:900px}}header+section{{overflow-x:auto}}.split,.sources{{grid-template-columns:1fr}}}}

/* Editorial reading layer: semantic answer elements now carry the hierarchy. */
:root{{--paper:#edf3ee;--ink:#12241c;--pine:#155f4c;--leaf:#599b75;--line:#b8cbbd;--wash:#dce9df;--soft:#4d665a;--signal:#d27947;--deep:#0d2a22}}
body{{background:linear-gradient(135deg,#eef5f0 0%,#e8eee9 48%,#f6f1e9 100%);color:var(--ink)}}
main{{max-width:1180px;padding:32px}}
header{{position:relative;margin:0 -32px;padding:58px 32px 44px;color:#f1f6f1;background:radial-gradient(circle at 82% 18%,#2d725b 0,transparent 28%),linear-gradient(125deg,#0a241d,#164c3d 70%,#27644e);border:0;overflow:hidden}}
header:after{{content:"";position:absolute;right:-58px;bottom:-88px;width:270px;height:270px;border:1px solid rgba(255,255,255,.23);border-radius:50%;box-shadow:0 0 0 30px rgba(255,255,255,.05),0 0 0 61px rgba(255,255,255,.035)}}
header .eyebrow{{color:#a9d6b8}}header .lede{{color:#d5e7d8}}h1{{position:relative;z-index:1;max-width:880px;font-weight:600;letter-spacing:-.06em}}
h2{{margin-top:64px;font-size:2.05rem}}.split{{gap:54px}}.flow{{margin:38px 0 4px}}.flow rect{{fill:#f7fbf7;stroke:#b6cebc}}.flow .flow-label{{fill:#15372b}}.flow .flow-metric{{fill:#17664f}}
.notice{{padding:22px 24px;border-left:4px solid var(--signal);background:#fff5eb;color:#664735;box-shadow:0 10px 28px rgba(17,49,37,.06)}}
.qa{{grid-template-columns:64px minmax(0,1fr);gap:24px;padding:34px 0}}.qnum{{padding-top:5px;color:var(--signal);font-size:12px}}.question{{margin:0 0 18px;color:#245c49;font:700 clamp(1.25rem,2vw,1.7rem)/1.16 Arial,sans-serif;letter-spacing:-.035em}}.answer{{max-width:820px;font-size:1.04rem}}.answer>p:first-child{{font-size:1.13rem}}.answer p{{margin:0 0 1.05em}}.answer h2,.answer h3,.answer h4{{margin:1.8em 0 .65em;padding:0;border:0;color:#174e3e;font-family:Arial,sans-serif;letter-spacing:-.025em}}.answer h2{{font-size:1.52rem}}.answer h3{{font-size:1.23rem}}.answer h4{{font-size:1.05rem}}.answer ul,.answer ol{{margin:.3em 0 1.2em;padding-left:1.25em}}.answer li{{margin:.38em 0}}.answer hr{{height:1px;margin:2em 0;border:0;background:var(--line)}}.answer code{{padding:.12em .35em;border-radius:3px;background:#dcebe1;color:#154b3c;font:85% ui-monospace,SFMono-Regular,Consolas,monospace}}.answer pre{{margin:1.25em 0;padding:17px 19px;overflow:auto;border:1px solid #255a49;border-radius:8px;background:#112c24;color:#e7f1e9;line-height:1.45;box-shadow:0 12px 24px rgba(12,39,30,.12)}}.answer pre code{{padding:0;background:transparent;color:inherit}}.cites{{white-space:normal}}.cite{{margin:0 2px;padding:3px 6px;border:1px solid #bad1c1;border-radius:3px;background:#e3f0e6;color:#135943;font:600 11px/1.2 Arial,sans-serif;vertical-align:baseline}}.qa details{{margin-top:18px}}.qa summary{{font-weight:700}}.sources{{gap:18px}}.source{{padding:22px;border:1px solid #c5d6c8;border-radius:8px;background:rgba(252,255,252,.82);box-shadow:0 10px 24px rgba(17,49,37,.045)}}.source h3{{font-size:1.18rem}}.source footer{{padding-top:14px}}@media(max-width:720px){{main{{padding:18px}}header{{margin:0 -18px;padding:42px 18px 32px}}.qa{{grid-template-columns:1fr;gap:8px}}.qnum{{padding:0}}}}

.causal-map{{margin:2.1rem 0 2.3rem;padding:20px 20px 10px;border:1px solid #c7d9ca;border-radius:12px;background:linear-gradient(135deg,#f8fcf8,#eef7f0);box-shadow:0 18px 36px rgba(17,49,37,.08)}}
.causal-map figcaption{{display:flex;align-items:baseline;gap:12px;margin:0 7px 16px;font-family:Arial,sans-serif}}.causal-map figcaption span{{color:#a85532;font-size:11px;font-weight:800;letter-spacing:.13em;text-transform:uppercase}}.causal-map figcaption strong{{font-size:1.05rem;letter-spacing:-.02em}}.causal-map svg{{display:block;width:100%;height:auto}}.causal-map .causal-node rect{{stroke-width:1.5}}.causal-map .causal-step{{font:800 12px Arial,sans-serif;letter-spacing:.08em}}.causal-map .causal-label{{font:600 17px/1.2 Arial,sans-serif;letter-spacing:-.015em}}.causal-map .causal-link{{fill:none;stroke:#4a765f;stroke-width:2.25;stroke-linecap:round}}.causal-map #causal-arrow path{{fill:#4a765f}}.causal-map .causal-node-0 rect{{fill:#dcefe3;stroke:#60a77a}}.causal-map .causal-node-0 .causal-step{{fill:#277b52}}.causal-map .causal-node-0 .causal-label{{fill:#164c36}}.causal-map .causal-node-1 rect{{fill:#dcecf0;stroke:#5a98ad}}.causal-map .causal-node-1 .causal-step{{fill:#35758b}}.causal-map .causal-node-1 .causal-label{{fill:#1c4c60}}.causal-map .causal-node-2 rect{{fill:#f7ead8;stroke:#c99450}}.causal-map .causal-node-2 .causal-step{{fill:#a56826}}.causal-map .causal-node-2 .causal-label{{fill:#6e4319}}.causal-map .causal-node-3 rect{{fill:#eee3f3;stroke:#a476b5}}.causal-map .causal-node-3 .causal-step{{fill:#7d4d92}}.causal-map .causal-node-3 .causal-label{{fill:#51315f}}.causal-map .causal-node-4 rect{{fill:#f7e3e0;stroke:#c57968}}.causal-map .causal-node-4 .causal-step{{fill:#a45040}}.causal-map .causal-node-4 .causal-label{{fill:#6a3028}}@media(max-width:620px){{.causal-map{{margin-left:-4px;margin-right:-4px;padding:14px 8px 7px}}.causal-map figcaption{{display:block}}.causal-map figcaption strong{{display:block;margin-top:4px}}.causal-map .causal-label{{font-size:19px}}.causal-map svg{{min-width:620px}}.causal-map{{overflow-x:auto}}}}
</style></head><body><main><header><div class="eyebrow">NotebookLM HTML Atlas · {e(date.today().isoformat())}</div><h1>{e(title)}</h1><p class="lede">A portable view of source metadata, question answers, and the evidence chunks NotebookLM returned.</p></header><section>{flow(len(sources), len(qas), sum(map(len, excerpts.values())))}</section><section class="split"><div><h2>Source mix</h2>{bars or "No sources found."}</div><aside class="notice">The page preserves metadata and cited excerpts in the supplied exports. It does not download full PDFs, videos, or web pages, and it does not independently validate NotebookLM's claims.</aside></section><section><h2>Questions &amp; evidence</h2>{''.join(qa_markup) or '<p>No Q&amp;A exports included.</p>'}</section><section><h2>Source library</h2><div class="sources">{''.join(source_markup)}</div></section><footer>Generated locally from NotebookLM JSON exports. External links point to the original sources.</footer></main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a static NotebookLM HTML research report")
    parser.add_argument("--sources", required=True)
    parser.add_argument("--qa", action="append", default=[])
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.sources, encoding="utf-8") as handle:
        sources = json.load(handle)
    qas = []
    for path in args.qa:
        with open(path, encoding="utf-8") as handle:
            qas.append(json.load(handle))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(args.title, sources, qas), encoding="utf-8")
    print(f"CREATED: {output}")


if __name__ == "__main__":
    main()
