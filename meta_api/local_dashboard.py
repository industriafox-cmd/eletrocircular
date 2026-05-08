#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PORT = int(os.getenv("LOCAL_BI_PORT", "8788"))

def rows(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def num(v):
    try:
        return float(str(v or 0).replace(",", "."))
    except ValueError:
        return 0.0

def series(path: Path, since: str, until: str):
    return {r.get("name", "-"): int(num(r.get("value"))) for r in rows(path) if r.get("since") == since and r.get("until") == until}

def quality(since: str, until: str):
    for r in rows(DATA / "lead_quality_summary.csv"):
        if r.get("since") == since and r.get("until") == until:
            return {"leads": num(r.get("leads")), "valid_cnpj": num(r.get("valid_cnpj")), "cnpj_14": num(r.get("cnpj_14")), "blank_cnpj": num(r.get("blank_cnpj"))}
    return {"leads": 0, "valid_cnpj": 0, "cnpj_14": 0, "blank_cnpj": 0}

def sql(since: str, until: str):
    return sum(int(num(r.get("sql"))) for r in rows(ROOT / "sql_metrics.csv") if r.get("date_start") == since and r.get("date_stop") == until)

def campaign_rows(since: str):
    data = rows(DATA / "meta_campaign_export.csv")
    token = "MAIO26" if since[5:7] == "05" else "ABRIL26" if since[5:7] == "04" else ""
    filtered = [r for r in data if token and token in (r.get("Nome da campanha") or "").upper()]
    return filtered or data

def pnrs():
    monthly = rows(ROOT / "pnrs_monthly.csv")
    partners = rows(ROOT / "pnrs_partners.csv")
    total = next((r for r in monthly if r.get("month") == "TOTAL"), {})
    return {
        "monthly": monthly,
        "origin": rows(ROOT / "pnrs_origin.csv"),
        "operation": rows(ROOT / "pnrs_operation.csv"),
        "partners": partners,
        "summary": {
            "goal": num(total.get("planned")),
            "realized": num(total.get("realized")),
            "remaining": num(total.get("gap")),
            "achievement": num(total.get("achievement_rate")),
            "need_per_month": 1455,
            "partner_projection": num(next((r for r in partners if r.get("partner") == "TOTAL"), {}).get("projection")),
        },
    }

def payload(since: str, until: str):
    q = quality(since, until)
    campaigns = campaign_rows(since)
    spend = sum(num(r.get("Valor usado (BRL)")) for r in campaigns)
    impressions = sum(num(r.get("Impressões")) for r in campaigns)
    clicks = sum(num(r.get("Cliques no link")) for r in campaigns)
    leads = q["leads"] or sum(num(r.get("Resultados")) for r in campaigns if r.get("Tipo de resultado") == "Leads (formulário)")
    valid = q["valid_cnpj"]
    s = sql(since, until)
    return {
        "since": since,
        "until": until,
        "summary": {
            "spend": spend,
            "impressions": impressions,
            "link_clicks": clicks,
            "leads": leads,
            "valid_cnpj": valid,
            "cnpj_14": q["cnpj_14"],
            "blank_cnpj": q["blank_cnpj"],
            "sql": s,
            "cpl": spend / leads if leads else 0,
            "cpl_valid_cnpj": spend / valid if valid else 0,
            "valid_cnpj_rate": valid / leads * 100 if leads else 0,
            "lead_to_sql": s / leads * 100 if leads else 0,
            "cost_per_sql": spend / s if s else 0,
            "link_ctr": clicks / impressions * 100 if impressions else 0,
            "cpc_link": spend / clicks if clicks else 0,
        },
        "by_day": series(DATA / "lead_by_day.csv", since, until),
        "by_adset": series(DATA / "lead_by_adset.csv", since, until),
        "by_platform": series(DATA / "lead_by_platform.csv", since, until),
        "campaigns": campaigns,
        "commercial_actions": rows(ROOT / "comercial_actions.csv"),
        "pnrs": pnrs(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

HTML = """<!doctype html><html lang=pt-BR><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>EletroCircular BI</title><style>
body{margin:0;background:#f4f6f3;color:#17211b;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}header{background:white;border-bottom:1px solid #dbe2da;padding:18px 28px}.head{max-width:1280px;margin:auto;display:flex;justify-content:space-between;gap:16px;align-items:end}h1{margin:0;font-size:22px}.sub{color:#647067;font-size:13px}main{max-width:1280px;margin:auto;padding:20px 28px}.controls{display:flex;gap:10px;align-items:end}label{display:grid;gap:4px;color:#647067;font-size:12px}input,button{height:38px;border:1px solid #dbe2da;border-radius:6px;padding:0 10px}button{background:#12733b;color:white;font-weight:700}.hero,.triad{display:grid;grid-template-columns:1fr 2fr;gap:14px;margin-bottom:14px}.triad{grid-template-columns:repeat(3,1fr)}.panel,.card{background:white;border:1px solid #dbe2da;border-radius:8px;padding:14px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.label{color:#647067;font-size:12px}.value,.big{font-size:26px;font-weight:800}.pill{display:inline-block;border-radius:999px;color:white;padding:5px 9px;font-size:12px;font-weight:800}.bad{background:#a32929}.good{background:#12733b}.warn{background:#a46400}.info{background:#22577a}.step{border-radius:8px;padding:14px;background:#eef4f0;border:1px solid #c8ddd0}.alert{padding:12px;border-radius:8px;margin:8px 0;background:#fff0ee;border:1px solid #edb7ad}.barrow{display:grid;grid-template-columns:220px 1fr 54px;gap:10px;align-items:center;margin:8px 0;font-size:13px}.track{height:10px;background:#e7ece6;border-radius:99px;overflow:hidden}.fill{height:100%;background:#12733b}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:8px;border-bottom:1px solid #dbe2da;text-align:left}@media(max-width:900px){.head,.hero,.triad,.grid{display:grid;grid-template-columns:1fr}.controls{display:grid}}
</style></head><body><header><div class=head><div><h1>EletroCircular BI</h1><div class=sub>Mídia, qualidade, jornada comercial e PNRS</div></div><div class=controls><label>Início<input id=since type=date value=2026-05-01></label><label>Fim<input id=until type=date value=2026-05-08></label><button id=refreshBtn>Atualizar</button></div></div></header><main><section class=hero><div class=panel><span id=verdictPill class='pill info'>Carregando</span><h2 id=verdictTitle>-</h2><p id=verdictText class=sub>-</p></div><div class=panel><h2>Funil de saúde</h2><div class=grid><div class=step><div class=label>Investimento</div><div id=spend class=big>-</div></div><div class=step><div class=label>Leads</div><div id=leads class=big>-</div><div id=cpl class=sub>-</div></div><div class=step><div class=label>CNPJ válido</div><div id=cnpjRate class=big>-</div><div id=cplValid class=sub>-</div></div><div class=step><div class=label>Lead → SQL</div><div id=sqlRate class=big>-</div><div id=costSql class=sub>-</div></div></div></div></section><section class=triad><div class=panel><h2>Mídia</h2><div class=grid><div><div class=label>CTR link</div><div id=linkCtr class=value>-</div></div><div><div class=label>CPC link</div><div id=cpcLink class=value>-</div></div></div></div><div class=panel><h2>Qualidade</h2><div class=grid><div><div class=label>CNPJ válidos</div><div id=validCnpj class=value>-</div></div><div><div class=label>Sem CNPJ</div><div id=blankCnpj class=value>-</div></div></div></div><div class=panel><h2>Jornada</h2><div class=grid><div><div class=label>SQL</div><div id=sql class=value>-</div></div><div><div class=label>Status</div><div id=journeyStatus class=value>-</div></div></div></div></section><section class=panel><h2>Alertas</h2><div id=alerts></div></section><section class=panel><h2>Gargalos e plano comercial</h2><div id=actions></div></section><section class=panel><h2>PNRS: meta e ritmo</h2><div class=grid><div class=card><div class=label>Meta total</div><div id=pnrsGoal class=value>-</div></div><div class=card><div class=label>Realizado até abril</div><div id=pnrsRealized class=value>-</div></div><div class=card><div class=label>% da meta</div><div id=pnrsAchievement class=value>-</div></div><div class=card><div class=label>Necessidade/mês</div><div id=pnrsNeed class=value>-</div></div></div><div id=pnrsMonthly></div></section><section class=triad><div class=panel><h2>Leads por dia</h2><div id=dayBars></div></div><div class=panel><h2>Leads por conjunto</h2><div id=adsetBars></div></div><div class=panel><h2>Grandes parceiros</h2><div id=partnerBars></div></div></section><section class=panel><h2>Campanhas</h2><table><tbody id=campaignRows></tbody></table></section></main><script>
const brl=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}),pct=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2}),num=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:0});function n(v){return Number(v||0)}function bars(id,data){const e=Object.entries(data||{}),m=Math.max(...e.map(x=>n(x[1])),1);document.getElementById(id).innerHTML=e.map(([k,v])=>`<div class=barrow><div>${k}</div><div class=track><div class=fill style='width:${n(v)/m*100}%'></div></div><div>${num.format(v)}</div></div>`).join('')}async function refresh(){const r=await fetch(`/api/local?since=${since.value}&until=${until.value}`),d=await r.json(),s=d.summary;spend.textContent=brl.format(s.spend);leads.textContent=num.format(s.leads);cpl.textContent=`CPL ${brl.format(s.cpl)}`;cnpjRate.textContent=`${pct.format(s.valid_cnpj_rate)}%`;cplValid.textContent=`CPL válido ${brl.format(s.cpl_valid_cnpj)}`;sqlRate.textContent=`${pct.format(s.lead_to_sql)}%`;costSql.textContent=`Custo/SQL ${brl.format(s.cost_per_sql)}`;linkCtr.textContent=`${pct.format(s.link_ctr)}%`;cpcLink.textContent=brl.format(s.cpc_link);validCnpj.textContent=num.format(s.valid_cnpj);blankCnpj.textContent=num.format(s.blank_cnpj);sql.textContent=num.format(s.sql);journeyStatus.textContent=s.lead_to_sql<5?'Vazando':'OK';verdictPill.className=s.lead_to_sql<5?'pill bad':'pill good';verdictPill.textContent=s.lead_to_sql<5?'Atenção':'Saudável';verdictTitle.textContent=s.lead_to_sql<5?'Mídia saudável, jornada vazando':'Aquisição e conversão em faixa boa';verdictText.textContent='CPL e CNPJ válido são bons; a decisão depende de velocidade de atendimento, follow-up e SQL.';alerts.innerHTML=`<div class=alert><b>Jornada</b><br>Lead → SQL em ${pct.format(s.lead_to_sql)}%. O gargalo está depois do lead.</div>`;actions.innerHTML=(d.commercial_actions||[]).map(a=>`<div class=card><b>${a.title}</b><br><span class=sub>${a.impact}</span><br>Ação: ${a.action}</div>`).join('');const p=d.pnrs.summary;pnrsGoal.textContent=num.format(p.goal);pnrsRealized.textContent=num.format(p.realized);pnrsAchievement.textContent=`${pct.format(p.achievement)}%`;pnrsNeed.textContent=num.format(p.need_per_month);bars('pnrsMonthly',Object.fromEntries((d.pnrs.monthly||[]).filter(x=>x.month!='TOTAL'&&n(x.realized)).map(x=>[x.month,n(x.realized)])));bars('dayBars',d.by_day);bars('adsetBars',d.by_adset);bars('partnerBars',Object.fromEntries((d.pnrs.partners||[]).filter(x=>x.partner!='TOTAL').map(x=>[x.partner,n(x.projection)])));campaignRows.innerHTML=(d.campaigns||[]).map(c=>`<tr><td>${c['Nome da campanha']||'-'}</td><td>${c['Tipo de resultado']||'-'}</td><td>${brl.format(n(c['Valor usado (BRL)']))}</td><td>${num.format(n(c.Resultados))}</td></tr>`).join('')}refreshBtn.onclick=refresh;refresh();</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/local":
            q = parse_qs(parsed.query)
            self.send_json(payload(q.get("since", ["2026-05-01"])[0], q.get("until", ["2026-05-08"])[0]))
            return
        self.send_json({"error": "not found"}, 404)

def main():
    print(f"BI local rodando em http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
