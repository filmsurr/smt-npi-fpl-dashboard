#!/usr/bin/env python3
from __future__ import annotations
import json, math, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'rules_config.json').read_text(encoding='utf-8'))
DATA=ROOT/'dashboard_data.js'; CACHE=ROOT/'.fpl_cache'; BASE='https://fantasy.premierleague.com/api'
LEAGUE_ID=int(CONFIG['league']['league_id']); REFRESH_ALL='--refresh-all' in sys.argv


def api_get(path,retries=3):
    url=path if path.startswith('http') else BASE+path
    last=None
    for attempt in range(1,retries+1):
        try:
            req=Request(url,headers={'User-Agent':'Mozilla/5.0 SMT-NPI-FPL-Dashboard/2.1','Accept':'application/json'})
            with urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
        except (HTTPError,URLError,TimeoutError,json.JSONDecodeError) as e:
            last=e
            if attempt<retries: time.sleep(attempt)
    raise RuntimeError(f'FPL API error: {url} — {last}')

def cached_get(path,name):
    CACHE.mkdir(exist_ok=True); f=CACHE/name
    if f.exists() and not REFRESH_ALL:
        try:return json.loads(f.read_text())
        except Exception:pass
    d=api_get(path); f.write_text(json.dumps(d,ensure_ascii=False)); return d

def normalize_schedule():
    ps=CONFIG['penalty_system']; cur=1; out=[]
    for raw in ps['schedule']:
        p=dict(raw); c=int(p['gw_count']); teams=ps['penalty_teams_by_gw_count'].get(str(c))
        if teams is None: raise ValueError(f'Penalty teams not configured for {c} GW month')
        p['start_gw']=cur; p['end_gw']=cur+c-1; p['penalty_teams']=int(teams)
        p['penalty_pool_thb']=round(float(ps['season_target_thb'])*c/38)
        out.append(p); cur=p['end_gw']+1
    if cur-1!=38: raise ValueError(f'Penalty schedule covers {cur-1} GWs, expected 38')
    return out

SCHEDULE=normalize_schedule()

def get_bootstrap():
    d=api_get('/bootstrap-static/')
    names={x['id']:x.get('web_name') or f"Player {x['id']}" for x in d.get('elements',[])}
    finished=[e['id'] for e in d.get('events',[]) if e.get('finished')]
    return names,(max(finished) if finished else 0)

def get_league():
    page=1; allr=[]; meta=None
    while True:
        d=api_get(f'/leagues-classic/{LEAGUE_ID}/standings/?page_standings={page}')
        meta=meta or d.get('league',{}); s=d.get('standings',{}); allr+=s.get('results',[])
        if not s.get('has_next'):break
        page+=1
    managers=[]
    for r in allr:
        managers.append({'manager_id':r['entry'],'manager_name':r.get('player_name') or f"Entry {r['entry']}",'team_name':r.get('entry_name') or '', 'league_rank':r.get('rank'),'last_rank':r.get('last_rank')})
    managers.sort(key=lambda x:(x['league_rank'] or 9999,x['manager_name']))
    return meta or {},managers

def get_histories(managers,latest):
    rows=[]
    for i,m in enumerate(managers,1):
        print(f"[History {i}/{len(managers)}] {m['manager_name']}")
        d=api_get(f"/entry/{m['manager_id']}/history/")
        prev_total=0
        for g in sorted(d.get('current',[]),key=lambda x:x.get('event',0)):
            gw=int(g.get('event',0) or 0)
            if gw<=0 or gw>latest:continue
            raw=int(g.get('points',0) or 0); hit=int(g.get('event_transfers_cost',0) or 0); total=int(g.get('total_points',0) or 0)
            net=total-prev_total; expected=raw-hit; adjustment=net-expected; prev_total=total
            rows.append({'manager_id':m['manager_id'],'manager_name':m['manager_name'],'team_name':m['team_name'],'gw':gw,'gw_points':raw,'transfer_cost':hit,'net_gw_points':net,'score_adjustment':adjustment,'total_points':total,'team_value':round((g.get('value') or 0)/10,1),'overall_rank':g.get('overall_rank')})
    return rows

def get_captains(managers,latest,names):
    out=[]
    for gw in range(1,latest+1):
        print(f'[Captain] GW{gw}')
        live={x['id']:int(x.get('stats',{}).get('total_points',0) or 0) for x in cached_get(f'/event/{gw}/live/',f'live_{gw}.json').get('elements',[])}
        for m in managers:
            try:
                p=cached_get(f"/entry/{m['manager_id']}/event/{gw}/picks/",f"picks_{m['manager_id']}_{gw}.json")
                picks=p.get('picks',[]); mult=[x for x in picks if int(x.get('multiplier',0) or 0)>1]
                eff=max(mult,key=lambda x:int(x.get('multiplier',0) or 0)) if mult else next((x for x in picks if x.get('is_captain')),None)
                if not eff:continue
                pid=eff['element']; multiplier=int(eff.get('multiplier',0) or 0); raw=live.get(pid,0)
                out.append({'manager_id':m['manager_id'],'gw':gw,'captain':names.get(pid,f'Player {pid}'),'raw_points':raw,'multiplier':multiplier,'captain_points':raw*multiplier})
            except Exception as e: print('  captain warning:',m['manager_name'],gw,e)
    return out

def exact_split(pool,rows):
    total=sum(max(0,r['monthly_penalty_gap']) for r in rows)
    if total<=0:return [0]*len(rows)
    raw=[pool*max(0,r['monthly_penalty_gap'])/total for r in rows]; base=[math.floor(x) for x in raw]; rem=int(pool-sum(base))
    order=sorted(range(len(raw)),key=lambda i:(raw[i]-base[i],rows[i]['monthly_penalty_gap']),reverse=True)
    for i in order[:rem]:base[i]+=1
    return base

def build_penalty_period(history,managers,latest,p):
    if latest<p['start_gw']:return {'status':'not_started',**p,'entries':[]}
    through=min(latest,p['end_gw']); agg={m['manager_id']:{'manager_id':m['manager_id'],'manager_name':m['manager_name'],'team_name':m['team_name'],'raw_points':0,'transfer_hits':0,'monthly_points':0,'score_adjustment':0} for m in managers}
    for r in history:
        if p['start_gw']<=r['gw']<=through:
            a=agg[r['manager_id']]; a['raw_points']+=r['gw_points']; a['transfer_hits']+=r['transfer_cost']; a['monthly_points']+=r['net_gw_points']; a['score_adjustment']+=r['score_adjustment']
    ranked=sorted(agg.values(),key=lambda x:(x['monthly_points'],x['manager_name']),reverse=True); top=ranked[0]['monthly_points'] if ranked else 0
    n=min(p['penalty_teams'],len(ranked)); bottom=sorted(ranked,key=lambda x:(x['monthly_points'],x['manager_name']))[:n]
    if len(ranked)>n and n>0:
        cutoff=bottom[-1]['monthly_points']; next_score=sorted(ranked,key=lambda x:(x['monthly_points'],x['manager_name']))[n]['monthly_points']
        if cutoff==next_score:
            return {'status':'tie_review','reason':'Penalty cutoff is tied; league rule requires manual review.','top_score':top,'entries':[],**p}
    for r in bottom:r['monthly_penalty_gap']=max(0,top-r['monthly_points'])
    pays=exact_split(p['penalty_pool_thb'],bottom)
    for r,pay in zip(bottom,pays):r['penalty_thb']=pay
    bottom.sort(key=lambda x:(x['penalty_thb'],x['monthly_penalty_gap']),reverse=True)
    status='finalized' if latest>=p['end_gw'] else 'projected'
    return {'status':status,'top_score':top,'through_gw':through,'entries':bottom,'score_basis':'Official net FPL points after transfer-hit deductions',**p}

def mvp_counts(history,managers,through):
    counts={m['manager_id']:0 for m in managers}
    for gw in range(1,through+1):
        rows=[r for r in history if r['gw']==gw]
        if not rows:continue
        top=max(r['gw_points'] for r in rows)
        for r in rows:
            if r['gw_points']==top:counts[r['manager_id']]+=1
    return counts

def build_data(meta,managers,history,caps,latest):
    periods=[build_penalty_period(history,managers,latest,p) for p in SCHEDULE]
    ledger={m['manager_id']:{'manager_id':m['manager_id'],'manager_name':m['manager_name'],'times_penalized':0,'total_penalty_paid_thb':0} for m in managers}
    for p in periods:
        if p['status']=='finalized':
            for e in p['entries']:
                ledger[e['manager_id']]['times_penalized']+=1; ledger[e['manager_id']]['total_penalty_paid_thb']+=e['penalty_thb']
    mvp=mvp_counts(history,managers,latest); cap_tot={m['manager_id']:0 for m in managers}
    for c in caps:cap_tot[c['manager_id']]=cap_tot.get(c['manager_id'],0)+c['captain_points']
    latest_rows={r['manager_id']:r for r in history if r['gw']==latest}
    standings=[]
    for m in managers:
        r=latest_rows.get(m['manager_id']);
        if not r:continue
        standings.append({'league_rank':m['league_rank'],'previous_rank':m['last_rank'],'rank_change':None if m['last_rank'] is None else m['last_rank']-m['league_rank'],'manager_id':m['manager_id'],'manager_name':m['manager_name'],'team_name':m['team_name'],'gw_points':r['gw_points'],'net_gw_points':r['net_gw_points'],'transfer_cost':r['transfer_cost'],'total_points':r['total_points'],'team_value':r['team_value'],'captain_points_cumulative':cap_tot.get(m['manager_id'],0),'gw_mvp_wins_cumulative':mvp.get(m['manager_id'],0),'times_penalized':ledger[m['manager_id']]['times_penalized'],'total_penalty':ledger[m['manager_id']]['total_penalty_paid_thb']})
    standings.sort(key=lambda x:x['league_rank'])
    finalized=sum(p['penalty_pool_thb'] for p in periods if p['status']=='finalized'); current=next((p for p in periods if p['start_gw']<=latest<=p['end_gw']),None); projected=current['penalty_pool_thb'] if current and current['status']=='projected' else 0
    audits=[]; pools=sum(p['penalty_pool_thb'] for p in SCHEDULE)
    if pools!=CONFIG['penalty_system']['season_target_thb']:
        audits.append({'level':'warn','code':'PENALTY_ROUNDING_VARIANCE','message':f"Monthly rounded penalty pools total {pools} THB vs {CONFIG['penalty_system']['season_target_thb']} THB target ({pools-CONFIG['penalty_system']['season_target_thb']:+} THB)."})
    return {'status':'ok','version':'2.1-penalty-fix','updated_at':datetime.now(timezone.utc).isoformat(),'latest_gw':latest,'league':{'league_id':LEAGUE_ID,'league_name':meta.get('name') or CONFIG['league']['display_name'],'display_name':CONFIG['league']['display_name'],'season':CONFIG['league']['season'],'manager_count':len(managers)},'standings':standings,'penalty_periods':periods,'penalty_ledger':list(ledger.values()),'financial':{'season_target_thb':CONFIG['penalty_system']['season_target_thb'],'collected_penalty_thb':finalized,'projected_current_period_thb':projected,'remaining_thb':max(0,CONFIG['penalty_system']['season_target_thb']-finalized)},'audit':audits,'rules':CONFIG}

def main():
    print('='*68);print('SMT NPI FPL Dashboard updater v2.1 — penalty fix');print('League',LEAGUE_ID);print('='*68)
    try:
        names,latest=get_bootstrap(); meta,managers=get_league(); print(f"Managers: {len(managers)} | Latest completed: GW{latest}")
        history=get_histories(managers,latest); caps=get_captains(managers,latest,names); data=build_data(meta,managers,history,caps,latest)
        DATA.write_text('window.FPL_DASHBOARD_DATA = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
        print('SUCCESS: dashboard_data.js updated');return 0
    except Exception as e:
        print('ERROR:',e);return 1
if __name__=='__main__':sys.exit(main())
