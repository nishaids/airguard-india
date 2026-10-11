"""Preserve historical pages while moving production to the nationwide UI."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
app=root/"webapp/app"
research=app/"research/page.js"
research.parent.mkdir(exist_ok=True)
if not research.exists():
    previous=(app/"page.js").read_text(encoding="utf-8")
    previous=previous.replace('"./components/', '"../components/')
    previous=previous.replace('<div>', '<div><p role="note" className="research-notice">HISTORICAL REPLAY — NOT CURRENT AIR QUALITY. Legacy research using 2015–2020 observations and the original training cities.</p>',1)
    research.write_text(previous,encoding="utf-8")
for route in ("page.js","live/page.js"):
    prefix="./" if route=="page.js" else "../"
    (app/route).write_text(f'import NationwideDashboard from "{prefix}components/NationwideDashboard";\nexport default function Page() {{ return <NationwideDashboard />; }}\n',encoding="utf-8")
for route in ("forecast","city-atlas","model-insights","policy-simulator"):
    path=app/route/"page.js"
    content=path.read_text(encoding="utf-8")
    message='HISTORICAL REPLAY — NOT CURRENT AIR QUALITY. Legacy model / research record: 2015–2020, original training cities. SHAP shows model attribution, not causality.'
    if route=="policy-simulator":
        message='COUNTERFACTUAL SCENARIO · HISTORICAL RESEARCH. This recomputes indices after assumed concentration reductions; it does not establish the causal effect of a real policy.'
    banner='<p className="research-notice" role="note">'+message+'</p>'
    if route=="city-atlas":
        content=content.replace('import { useEffect, useState } from "react";', 'import { useEffect, useState } from "react";\nimport NationwideDashboard from "../components/NationwideDashboard";')
        content=content.replace('if (!data) return <Loading />;', 'if (!data) return <><NationwideDashboard atlas /><Loading /></>;')
        banner='<NationwideDashboard atlas />'+banner
    if route=="model-insights":
        banner+='<p>Production uses live CAMS concentrations and a separate CPCB-style engine. The live forecast track record appears on <a href="/live">Live air quality</a> once adequate measured pairs exist.</p>'
    content=content.replace('    <div>', '    <div>'+banner,1)
    if route=="forecast":
        content=content.replace('Tomorrow’s AQI','Historical next-day AQI').replace("Tomorrow's AQI","Historical next-day AQI").replace('Next-day prediction','Historical next-day replay')
    path.write_text(content,encoding="utf-8")
for path in (root/"webapp/api").glob("*.py"):
    content=path.read_text(encoding="utf-8")
    content=content.replace('        self.send_header("Access-Control-Allow-Origin", "*")\n','')
    path.write_text(content,encoding="utf-8")
config=root/"webapp/vercel.json"
data=json.loads(config.read_text())
data["functions"]={"api/**/*.py":{"maxDuration":60,"includeFiles":"api/_bundle/**"}}
config.write_text(json.dumps(data,indent=2)+'\n')
