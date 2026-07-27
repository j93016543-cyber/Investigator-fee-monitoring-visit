#!/usr/bin/env python3
"""
대시보드 빌드: data/store.json + _template.html + app.js  ->  dashboard/index.html
(자체 완결형 HTML — Artifact 로 게시 가능)

사용법:  python3 dashboard/build.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dashboard"

store = json.loads((ROOT / "data" / "store.json").read_text(encoding="utf-8"))
tpl = (DASH / "_template.html").read_text(encoding="utf-8")
app = (DASH / "app.js").read_text(encoding="utf-8")

# </script> 가 데이터 안에 있으면 조기 종료되므로 escape
data_json = json.dumps(store, ensure_ascii=False).replace("</", "<\\/")

html = tpl.replace("/*__DATA__*/", data_json).replace("/*__JS__*/", app)
out = DASH / "index.html"
out.write_text(html, encoding="utf-8")
print(f"빌드 완료: {out}  ({len(html):,} bytes)")
