# Renders the end card and the section labels as 1920x1080 PNGs with headless Chrome.
import pathlib, subprocess

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUT = pathlib.Path(__file__).parent / "cards"
OUT.mkdir(exist_ok=True)

FONT = "font-family:'Segoe UI',Arial,sans-serif;"

END = f"""<!doctype html><html><body style="margin:0;width:1920px;height:1080px;background:#0f1115;color:#f5f5f2;{FONT}display:flex;align-items:center;justify-content:center">
<div style="width:1500px">
  <div style="font-size:150px;font-weight:800;letter-spacing:-4px;line-height:1">pivot</div>
  <div style="font-size:46px;margin-top:18px;color:#d6d6d0">The moments that changed the match, and why</div>
  <div style="height:6px;width:160px;background:#facc15;margin:56px 0 48px"></div>
  <div style="font-size:34px;line-height:1.7;color:#e8e8e2">
    <b>Azure AI Foundry</b>: models for the Judge, Explainer and Comparator agents<br>
    <b>Microsoft Agent Framework</b>: the detect workflow, with rewrite loop and fallback<br>
    <b>Azure Cosmos DB</b>: results &nbsp;·&nbsp; <b>Azure Blob Storage</b>: match library
  </div>
  <div style="font-size:36px;margin-top:52px;color:#facc15;font-weight:600">pivot.in-stacks.com &nbsp;·&nbsp; github.com/neubayarea/Pivot</div>
  <div style="font-size:28px;margin-top:22px;color:#a9a9a2">All clubs, players and matches are synthetic.</div>
</div></body></html>"""

def label(text, sub=""):
    sub_html = f'<span style="font-weight:500;color:#d6d6d0;margin-left:14px">{sub}</span>' if sub else ""
    return f"""<!doctype html><html><body style="margin:0;width:1920px;height:1080px;background:transparent;{FONT}">
<div style="position:absolute;left:28px;bottom:26px;background:rgba(15,17,21,.86);color:#fff;border-radius:12px;padding:12px 22px;font-size:30px;font-weight:700;box-shadow:0 4px 18px rgba(0,0,0,.3)">
<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#facc15;margin-right:14px;vertical-align:middle"></span>{text}{sub_html}</div></body></html>"""

TITLE = f"""<!doctype html><html><body style="margin:0;width:1920px;height:1080px;background:transparent;{FONT}">
<div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);background:rgba(15,17,21,.9);color:#fff;border-radius:24px;padding:46px 70px;text-align:center;box-shadow:0 10px 40px rgba(0,0,0,.35)">
<div style="font-size:120px;font-weight:800;letter-spacing:-3px;line-height:1">pivot</div>
<div style="font-size:40px;margin-top:16px;color:#e2e2dc">The moments that changed the match, and why</div></div></body></html>"""

cards = {
    "end": END,
    "title": TITLE,
    "l_livefan": label("Live", "Fan view"),
    "l_liveana": label("Live", "Analyst view"),
    "l_explain": label("Explain", "Judge, Explainer and Verifier agents"),
    "l_personal": label("Personalise", "your club, your language, your player"),
    "l_wifan": label("What if", "Fan view"),
    "l_wiana": label("What if", "Analyst view"),
    "l_report": label("Analyst report", "after full time"),
}
for name, html in cards.items():
    src = OUT / f"{name}.html"
    src.write_text(html, encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--default-background-color=00000000", "--window-size=1920,1080",
                    f"--screenshot={OUT / (name + '.png')}", src.as_uri()],
                   check=True, capture_output=True, timeout=60)
print("cards:", ", ".join(cards))
