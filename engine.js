(function(root){
'use strict';
const sum=(a)=>a.reduce((s,x)=>s+x,0);
function sharePenalty(rows,slots){
 const sorted=[...rows].sort((a,b)=>a.points-b.points); const out=[];let pos=0;
 while(pos<sorted.length){let end=pos+1;while(end<sorted.length&&sorted[end].points===sorted[pos].points)end++;
 const occupied=slots.slice(pos,end),amount=sum(occupied)/(end-pos);
 for(let i=pos;i<end;i++)out.push({...sorted[i],amount,positions:occupied.length?`${pos+1}–${Math.min(end,slots.length)}`:'—',tied:end-pos>1});pos=end;
 }
 return out;
}
function penalty(rows,n,pool){
 const sorted=[...rows].sort((a,b)=>a.points-b.points),top=Math.max(...rows.map(x=>x.points));
 const gaps=sorted.slice(0,n).map(x=>Math.max(0,top-x.points)),total=sum(gaps);
 // All-equal standings still occupy the configured slots, shared by everyone.
 return sharePenalty(rows,gaps.map(g=>total?pool*g/total:pool/Math.max(1,gaps.length)));
}
function normalize(config){
 const smt=!!config.league,prize=smt?config.prize_system:config;
 const schedule=smt?config.penalty_system.schedule:config.penalty_schedule;let cursor=1;
 return {name:smt?config.league.display_name:config.brand_name,id:smt?config.league.league_id:config.league_id,season:smt?config.league.season:config.season,target:smt?prize.season_target_thb:config.total_prize_target_thb,cap:smt?prize.max_prizes_per_manager:config.max_prizes_per_manager,manualEqual:smt&&prize.equal_value_conflict_policy==='manual_review',prizes:prize.prizes||[],schedule:schedule.map(p=>{const rule=smt?{penalty_teams:config.penalty_system.penalty_teams_by_gw_count[p.gw_count],penalty_pool_thb:Math.round(config.penalty_system.season_target_thb*p.gw_count/38)}:config.penalty_rules_by_gw_count[p.gw_count];const x={...p,...rule,start_gw:cursor,end_gw:cursor+p.gw_count-1};cursor+=p.gw_count;return x;})};
}
function allocate(defs,managers,cap,manualEqual){
 const counts={},awards=[];const ordered=[...defs].sort((a,b)=>b.amount_thb-a.amount_thb||(a.priority??defs.indexOf(a))-(b.priority??defs.indexOf(b)));
 const metric=(m,p)=>p.metric==='season_rank'?-m.rank:p.metric==='captain_points'?m.captain:p.metric==='gw_mvp_wins'?m.mvp:p.metric==='best_single_gw_points'||p.metric==='best_gw_points'?m.best:m.value;
 for(const p of ordered){let candidates=[...managers].filter(m=>metric(m,p)!=null).sort((a,b)=>metric(b,p)-metric(a,p));if(p.metric==='season_rank')candidates=candidates.filter(m=>m.rank>=p.target_rank);
 let winner=null,reason='',status='Not configured';const skipped=[];
 if(cap==null){reason='Maximum prize rule is Not configured';}
 else {for(let i=0;i<candidates.length;i++){
 const m=candidates[i];if((counts[m.id]||0)>=cap){skipped.push(m.name);continue;}
 const tie=candidates.filter(x=>metric(x,p)===metric(m,p)&&((counts[x.id]||0)<cap));
 let resolved=tie;
 for(const key of p.tie_breakers||[]){const v=x=>key==='season_total_points'?x.total:key==='best_single_gw_points'?x.best:null;if(tie.every(x=>v(x)!=null)){const best=Math.max(...resolved.map(v));resolved=resolved.filter(x=>v(x)===best);}}
 if(resolved.length>1){status='Tie pending';reason='No further prize tiebreak is configured';break;}
 const selected=resolved[0];
 if(manualEqual){const leads=ordered.filter(q=>q.amount_thb===p.amount_thb&&q.metric!=='season_rank'&&metric(selected,q)!=null&&managers.every(x=>metric(x,q)==null||metric(selected,q)>=metric(x,q)));if(leads.length>cap-(counts[selected.id]||0)){status='Manual review';reason='Equal-value prize conflict requires a league decision';break;}}
 winner=selected;counts[winner.id]=(counts[winner.id]||0)+1;status=skipped.length?'Passed down':'Eligible';reason=skipped.length?`${skipped.join(', ')} reached the ${cap}-prize limit; next eligible winner: ${winner.name}`:'Current eligible leader';break;
 }if(!winner&&!reason){status='Unallocated';reason='No eligible candidate available';}}
 awards.push({...p,winner,status,reason,leader:candidates[0]||null,stat:winner?metric(winner,p):null});
 }
 return defs.map(p=>awards.find(a=>a.key===p.key));
}
function build(d,raw,payments={penalties:[],prizes:[]}){
 const c=normalize(raw),warnings=[],history=d.history||[],caps=d.captain_history||[],latest=d.latest_gw||0;
 const managers=(d.standings||[]).map(x=>({id:x.manager_id,name:x.manager_name||x.manager,team:x.team_name||x.team,rank:x.league_rank||x.rank,move:x.rank_change,total:x.total_points,gw:x.gw_points,hit:x.transfer_cost,captain:x.captain_points_cumulative??x.captain_points,mvp:x.gw_mvp_wins_cumulative??x.gw_mvp_wins,value:x.team_value,best:x.best_gw_points??(history.length?Math.max(...history.filter(h=>h.manager_id===x.manager_id).map(h=>h.gw_points)):null)}));
 if(new Set(managers.map(m=>m.id)).size!==managers.length)warnings.push('Duplicate manager IDs');
 if(managers.some(m=>!Number.isInteger(m.id)||m.id<=0))warnings.push('Missing or invalid manager ID');
 if(!Number.isInteger(c.id)||c.id<=0)warnings.push('Invalid league ID');
 if(sum(c.prizes.map(p=>p.percent||0))!==100)warnings.push('Prize percentages do not total 100%');
 if(Math.abs(sum(c.prizes.map(p=>p.amount_thb||0))-c.target)>.001)warnings.push('Prize amounts differ from target');
 if(sum(c.schedule.map(p=>p.gw_count))!==38)warnings.push('Monthly mapping does not cover 38 GWs');
 const pools=sum(c.schedule.map(p=>p.penalty_pool_thb||0));if(pools!==c.target)warnings.push(`Monthly pools total ฿${pools}; prize target ฿${c.target}`);
 if(!history.length)warnings.push('Saved snapshot lacks full GW history. Run the updated manual updater to verify historical calculations.');
 if(history.some(h=>!Number.isInteger(h.transfer_cost)||h.transfer_cost<0||h.transfer_cost%4))warnings.push('Invalid transfer-hit cost');
 for(const kind of ['penalties','prizes'])for(const entry of payments[kind]||[]){if(!managers.some(m=>m.id===entry.manager_id)||!Number.isFinite(entry.amount_thb)||entry.amount_thb<0)throw Error('Invalid payment record: manager ID or amount');}
 const ids=managers.map(m=>m.id);for(const id of ids)if(history.length){const gws=history.filter(h=>h.manager_id===id).map(h=>h.gw);if(new Set(gws).size!==gws.length)warnings.push(`Duplicate GW for entry ${id}`);if(Array.from({length:latest},(_,i)=>i+1).some(g=>!gws.includes(g)))warnings.push(`Missing Gameweek for entry ${id}`);}
 if(history.length&&caps.length!==history.length)warnings.push('Captain data incomplete; captain prize needs review');
 const periods=c.schedule.map(p=>{const through=Math.min(latest,p.end_gw),started=latest>=p.start_gw;let rows=[],verified=false;
 if(started&&history.length){verified=managers.every(m=>Array.from({length:through-p.start_gw+1},(_,i)=>p.start_gw+i).every(g=>history.some(h=>h.manager_id===m.id&&h.gw===g)));
 rows=managers.map(m=>{const hs=history.filter(h=>h.manager_id===m.id&&h.gw>=p.start_gw&&h.gw<=through);return {...m,raw:sum(hs.map(h=>h.gw_points)),hits:sum(hs.map(h=>h.transfer_cost)),points:sum(hs.map(h=>h.net_gw_points))};});
 }else if(started){const old=(d.penalty_system?.periods||[]).find(x=>x.start_gw===p.start_gw);if(old?.monthly_ranking)rows=old.monthly_ranking.map(r=>({...managers.find(m=>m.id===r.manager_id),raw:r.raw_points,hits:r.transfer_hits,points:r.net_points}));}
 let status=!started?'Not started':verified?(through===p.end_gw?'Finalized':'Projected'):'Unverified snapshot';
 if(rows.length&&p.penalty_teams!=null&&p.penalty_pool_thb!=null)rows=penalty(rows,Math.min(p.penalty_teams,rows.length),p.penalty_pool_thb).sort((a,b)=>b.points-a.points);
 else if(started)warnings.push(`${p.month}: complete monthly ranking unavailable; penalty calculation withheld`);
 if(rows.length&&Math.abs(sum(rows.map(r=>r.amount))-p.penalty_pool_thb)>.00001)warnings.push(`${p.month}: penalty money conservation failed`);
 return {...p,status,rows,verified,through};});
 const prizes=allocate(c.prizes,managers,c.cap,c.manualEqual);if(history.length&&caps.length!==history.length){for(const p of prizes)if(p.metric==='captain_points'){p.winner=null;p.status='Data warning';p.reason='Captain history incomplete';}}
 const money=managers.map(m=>{const assessed=sum(periods.filter(p=>p.status==='Finalized').flatMap(p=>p.rows.filter(r=>r.id===m.id).map(r=>r.amount)));const paid=sum((payments.penalties||[]).filter(p=>p.manager_id===m.id).map(p=>p.amount_thb));const won=sum((payments.prizes||[]).filter(p=>p.manager_id===m.id&&p.status==='finalized').map(p=>p.amount_thb));return {...m,assessed,paid,outstanding:assessed-paid,won,projected:sum(prizes.filter(p=>p.winner?.id===m.id).map(p=>p.amount_thb)),net:won-paid};});
 if(money.some(m=>m.outstanding<-.01))warnings.push('Recorded payment exceeds verified assessed penalties');
 return {c,managers,periods,prizes,money,history,caps,warnings:[...new Set(warnings)],latest,updated:d.updated_at};
}
root.FPLEngine={sharePenalty,penalty,normalize,allocate,build};if(typeof module!=='undefined')module.exports=root.FPLEngine;
})(typeof window==='undefined'?globalThis:window);
