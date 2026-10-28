#!/usr/bin/env python3
"""Render docs/architecture.md and docs/adr/*.md into one readable HTML page.

Usage: python3 scripts/build_docs.py [--out docs/site/architecture.html]
Requires pandoc on PATH. Mermaid fences become <pre class="mermaid"> blocks.
"""
from __future__ import annotations

import argparse
import html
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CSS = """
/* Layout: 技术规格文档 —— 左侧粘性目录 + 右侧正文，宽表格与图在各自容器内横向滚动 */
:root{
  --bg:#F3F5F1; --surface:#FFFFFF; --line:#D5DDD3; --fg:#17231C; --muted:#5A6A5F;
  --pitch:#1E6B45; --pitch-soft:#E1EEE5; --plum:#4A1D57; --code:#EEF2EC;
  --display:"Barlow Condensed","Noto Sans SC",system-ui,sans-serif;
  --body:"Noto Sans SC",-apple-system,"PingFang SC",system-ui,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#101612; --surface:#18201B; --line:#2C3830; --fg:#E4EBE5; --muted:#9AAA9F;
  --pitch:#5CC38C; --pitch-soft:#1B3125; --plum:#D7A6E6; --code:#1D2621; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#101612; --surface:#18201B; --line:#2C3830; --fg:#E4EBE5; --muted:#9AAA9F;
  --pitch:#5CC38C; --pitch-soft:#1B3125; --plum:#D7A6E6; --code:#1D2621; color-scheme:dark}
body{background:var(--bg);color:var(--fg);font-family:var(--body);font-size:15px;line-height:1.75;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0 80px}
.layout{max-width:1220px;margin:0 auto;display:grid;grid-template-columns:230px minmax(0,1fr);gap:44px}
aside{position:sticky;top:env(safe-area-inset-top,0px);align-self:start;max-height:100vh;overflow:auto;padding-block:36px 24px}
aside .label{font-family:var(--mono);font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
aside ol{list-style:none;margin:0;padding:0;display:grid;gap:1px;font-size:13.5px}
aside a{display:block;color:var(--muted);text-decoration:none;padding:3px 0 3px 10px;border-left:2px solid var(--line)}
aside a:hover,aside a:focus-visible{color:var(--pitch);border-left-color:var(--pitch);outline:none}
aside a.sub{padding-left:22px;font-size:12.5px}
main{min-width:0;padding-block:36px 0}
h1,h2,h3{font-family:var(--display);line-height:1.2;text-wrap:balance;scroll-margin-top:12px}
h1{font-size:clamp(38px,6vw,58px);font-weight:800;margin:0 0 12px;text-transform:uppercase;letter-spacing:.01em}
h2{font-size:28px;font-weight:700;margin:48px 0 14px;padding-top:24px;border-top:2px solid var(--line)}
h3{font-size:20px;font-weight:700;margin:28px 0 10px}
p,ul,ol{max-width:76ch}
p{margin:0 0 12px}
ul,ol{padding-left:1.25em;margin:0 0 12px}
li{margin:2px 0}
a{color:var(--pitch)}
blockquote{margin:0 0 20px;padding:10px 16px;border-left:3px solid var(--pitch);background:var(--pitch-soft);color:var(--fg);max-width:none}
blockquote p{margin:0}
code{font-family:var(--mono);font-size:.86em;background:var(--code);padding:1px 5px;border-radius:3px}
pre{background:var(--surface);border:1px solid var(--line);padding:14px 16px;overflow-x:auto;font-size:12.8px;line-height:1.6;margin:0 0 16px}
pre code{background:none;padding:0;font-size:inherit}
pre.mermaid{background:var(--surface);text-align:center;padding:16px;font-family:var(--body)}
.scroll{overflow-x:auto;border:1px solid var(--line);background:var(--surface);margin:0 0 16px}
table{border-collapse:collapse;width:100%;font-size:13.8px}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
th{font-family:var(--mono);font-size:11.5px;letter-spacing:.05em;color:var(--muted);font-weight:600;white-space:nowrap;background:var(--bg)}
section.adr{border-top:1px dashed var(--line);margin-top:28px}
section.adr h2{border-top:0;margin-top:20px;padding-top:12px;font-size:23px}
.appendix-head{margin-top:64px}
.meta-foot{color:var(--muted);font-size:13px;margin-top:40px}
@media (max-width:900px){
  .layout{grid-template-columns:1fr;gap:0}
  aside{position:static;max-height:none;padding-block:20px 0}
  aside ol{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
}
"""

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800'
    '&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap">'
)

SCRIPT = """
<script>
document.querySelectorAll('aside a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const el = document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
    if (!el) return;
    e.preventDefault();
    el.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  });
});
</script>
"""


def pandoc(md: Path, shift: int = 0) -> str:
    cmd = ["pandoc", str(md), "-f", "gfm", "-t", "html5", "--wrap=none", "--syntax-highlighting=none"]
    if shift:
        cmd.append(f"--shift-heading-level-by={shift}")
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def polish(fragment: str) -> str:
    # Mermaid wants the diagram text directly inside <pre class="mermaid">.
    fragment = re.sub(r'<pre class="mermaid"><code>(.*?)</code></pre>',
                      r'<pre class="mermaid">\1</pre>', fragment, flags=re.S)
    fragment = re.sub(r"(<table>.*?</table>)", r'<div class="scroll">\1</div>', fragment, flags=re.S)
    fragment = re.sub(r'href="adr/(\d{4})-[^"]+\.md"', r'href="#adr-\1"', fragment)
    fragment = fragment.replace('href="adr/"', 'href="#adr-appendix"')
    return fragment


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DOCS / "site" / "architecture.html"))
    args = ap.parse_args()

    body = polish(pandoc(DOCS / "architecture.md"))
    toc = [(m.group(1), re.sub("<.*?>", "", m.group(2)), False)
           for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', body)]

    adr_sections = []
    toc.append(("adr-appendix", "附录：ADR 全文", False))
    for path in sorted((DOCS / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")):
        num = path.name[:4]
        frag = polish(pandoc(path, shift=1))
        title = re.search(r"<h2[^>]*>(.*?)</h2>", frag, flags=re.S)
        label = re.sub("<.*?>", "", title.group(1)) if title else f"ADR-{num}"
        adr_sections.append(f'<section class="adr" id="adr-{num}">{frag}</section>')
        toc.append((f"adr-{num}", label.split("：")[0], True))

    toc_html = "\n".join(
        f'<li><a class="{"sub" if sub else ""}" href="#{html.escape(i)}">{html.escape(t)}</a></li>'
        for i, t, sub in toc
    )
    page = f"""<title>Pivot 架构设计</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='#121418'/%3E%3CclipPath id='fv-ball'%3E%3Ccircle cx='50' cy='50' r='36.0'/%3E%3C/clipPath%3E%3Ccircle cx='50' cy='50' r='36.0' fill='#FFFFFF'/%3E%3Cg clip-path='url%28#fv-ball%29' fill='#121418' stroke='#121418' stroke-width='2.7' stroke-linejoin='round'%3E%3Cpolygon points='50.0,22.0 40.2,14.9 43.9,3.3 56.1,3.3 59.8,14.9'/%3E%3Cline x1='50.0' y1='36.2' x2='50.0' y2='22.0'/%3E%3Cpolygon points='76.6,41.4 80.4,29.8 92.5,29.8 96.3,41.4 86.5,48.5'/%3E%3Cline x1='63.1' y1='45.7' x2='76.6' y2='41.4'/%3E%3Cpolygon points='66.4,72.6 78.6,72.6 82.4,84.2 72.5,91.4 62.7,84.2'/%3E%3Cline x1='58.1' y1='61.2' x2='66.4' y2='72.6'/%3E%3Cpolygon points='33.6,72.6 37.3,84.2 27.5,91.4 17.6,84.2 21.4,72.6'/%3E%3Cline x1='41.9' y1='61.2' x2='33.6' y2='72.6'/%3E%3Cpolygon points='23.4,41.4 13.5,48.5 3.7,41.4 7.5,29.8 19.6,29.8'/%3E%3Cline x1='36.9' y1='45.7' x2='23.4' y2='41.4'/%3E%3C/g%3E%3Cpolygon points='50.0,36.2 63.1,45.7 58.1,61.2 41.9,61.2 36.9,45.7' fill='#FFCC1F' stroke='#121418' stroke-width='2.7' stroke-linejoin='round'/%3E%3Ccircle cx='50' cy='50' r='38.5' fill='none' stroke='#F4F5F7' stroke-width='4.9'/%3E%3C/svg%3E">
{FONTS}
<style>{CSS}</style>
<div class="layout">
<aside><p class="label">目录</p><ol>
{toc_html}
</ol></aside>
<main>
{body}
<h2 id="adr-appendix" class="appendix-head">附录：ADR 全文</h2>
<p>以下内容由仓库 <code>docs/adr/</code> 中的决策记录自动生成，与源文件保持一致。</p>
{''.join(adr_sections)}
<p class="meta-foot">由 scripts/build_docs.py 从 docs/architecture.md 与 docs/adr/ 生成。</p>
</main>
</div>
{SCRIPT}"""
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(page):,} bytes, {len(adr_sections)} ADRs)")


if __name__ == "__main__":
    main()
