#!/usr/bin/env python3
"""SMT NPI FPL dashboard data engine.

Reads rules_config.json, downloads official FPL data, validates the data/rules,
calculates historical snapshots, prize projections, monthly penalties, and
writes dashboard_data.js for static hosting.

No third-party Python packages are required.
"""

from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "rules_config.json"
DATA_FILE = ROOT / "dashboard_data.js"
CACHE_DIR = ROOT / ".fpl_cache"
BASE = "https://fantasy.premierleague.com/api"
REFRESH_ALL = "--refresh-all" in sys.argv
USER_AGENT = "Mozilla/5.0 SMT-NPI-FPL-Dashboard/2.0"


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def read_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def normalize_config(raw: dict) -> dict:
    config = json.loads(json.dumps(raw))
    penalty = config.get("penalty_system", {})
    if not penalty.get("enabled"):
        return config

    target = float(penalty.get("season_target_thb") or 0)
    team_map = penalty.get("penalty_teams_by_gw_count", {})
    cursor = 1
    normalized = []
    for item in penalty.get("schedule", []):
        row = dict(item)
        count = int(row["gw_count"])
        row["start_gw"] = cursor
        row["end_gw"] = cursor + count - 1
        row["penalty_teams"] = team_map.get(str(count))
        row["penalty_pool_thb"] = round_half_up(target * count / 38) if target else 0
        normalized.append(row)
        cursor = row["end_gw"] + 1
    penalty["schedule"] = normalized
    return config


CONFIG = normalize_config(read_config())
LEAGUE_ID = int(CONFIG["league"]["league_id"])


def api_get(path: str, retries: int = 3):
    url = path if path.startswith("http") else BASE + path
    last_error = None
    for attempt in range(1, retries + 1):
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(attempt)
    raise RuntimeError(f"FPL API unavailable: {url} -> {last_error}")


def cached_get(path: str, name: str):
    CACHE_DIR.mkdir(exist_ok=True)
    fp = CACHE_DIR / name
    if fp.exists() and not REFRESH_ALL:
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = api_get(path)
    fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def get_bootstrap():
    data = api_get("/bootstrap-static/")
    names = {p["id"]: p.get("web_name") or f"Player {p['id']}" for p in data.get("elements", [])}
    finished = [e["id"] for e in data.get("events", []) if e.get("finished")]
    latest_gw = max(finished) if finished else 0
    return data, names, latest_gw


def get_league_managers():
    managers = []
    page = 1
    league_meta = None
    while True:
        data = api_get(f"/leagues-classic/{LEAGUE_ID}/standings/?page_standings={page}")
        league_meta = league_meta or data.get("league", {})
        standings = data.get("standings", {})
        for row in standings.get("results", []):
            managers.append({
                "manager_id": row["entry"],
                "manager_name": row.get("player_name") or f"Entry {row['entry']}",
                "team_name": row.get("entry_name") or "",
                "api_rank": row.get("rank"),
                "api_last_rank": row.get("last_rank"),
                "api_total": row.get("total"),
                "api_gw_points": row.get("event_total"),
            })
        if not standings.get("has_next"):
            break
        page += 1
    if not managers:
        raise RuntimeError(f"League {LEAGUE_ID} returned no managers.")
    return league_meta or {}, managers


def get_histories(managers, latest_gw):
    histories = {}
    for i, m in enumerate(managers, start=1):
        print(f"[History {i}/{len(managers)}] {m['manager_name']}")
        data = api_get(f"/entry/{m['manager_id']}/history/")
        histories[m["manager_id"]] = [r for r in data.get("current", []) if r.get("event", 0) <= latest_gw]
    return histories


def get_live_stats(gw):
    data = cached_get(f"/event/{gw}/live/", f"live_gw_{gw}.json")
    return {
        x["id"]: {
            "total_points": x.get("stats", {}).get("total_points", 0),
            "minutes": x.get("stats", {}).get("minutes", 0),
        }
        for x in data.get("elements", [])
    }


def get_captain_rows(managers, player_names, latest_gw):
    rows = []
    for gw in range(1, latest_gw + 1):
        print(f"[Captain] GW{gw}")
        live = get_live_stats(gw)
        for m in managers:
            mid = m["manager_id"]
            picks_data = cached_get(
                f"/entry/{mid}/event/{gw}/picks/",
                f"picks_{mid}_gw_{gw}.json",
            )
            picks = picks_data.get("picks", [])
            captain = next((p for p in picks if p.get("is_captain")), None)
            vice = next((p for p in picks if p.get("is_vice_captain")), None)
            if not captain:
                continue
            cstats = live.get(captain["element"], {"total_points": 0, "minutes": 0})
            vstats = live.get(vice["element"], {"total_points": 0, "minutes": 0}) if vice else {"total_points": 0, "minutes": 0}
            if cstats.get("minutes", 0) > 0:
                effective = captain
                stats = cstats
                source = "captain"
            elif vice and vstats.get("minutes", 0) > 0:
                effective = vice
                stats = vstats
                source = "vice_captain"
            else:
                effective = captain
                stats = cstats
                source = "captain_no_show"
            multiplier = 3 if picks_data.get("active_chip") == "3xc" else 2
            pid = effective["element"]
            raw = stats.get("total_points", 0)
            rows.append({
                "manager_id": mid,
                "gw": gw,
                "captain_player": player_names.get(pid, f"Player {pid}"),
                "captain_raw_points": raw,
                "captain_multiplier": multiplier,
                "captain_points": raw * multiplier,
                "captain_source": source,
                "active_chip": picks_data.get("active_chip"),
            })
    return rows


def period_for_gw(gw):
    for p in CONFIG.get("penalty_system", {}).get("schedule", []):
        if p["start_gw"] <= gw <= p["end_gw"]:
            return p
    return None


def compute_base_rows(managers, histories, captain_rows, latest_gw):
    manager_by_id = {m["manager_id"]: m for m in managers}
    captain_by_key = {(r["manager_id"], r["gw"]): r for r in captain_rows}
    raw = []
    for mid, history in histories.items():
        m = manager_by_id[mid]
        for h in history:
            c = captain_by_key.get((mid, h["event"]), {})
            raw.append({
                "manager_id": mid,
                "manager_name": m["manager_name"],
                "team_name": m["team_name"],
                "gw": h["event"],
                "gw_points": h.get("points", 0),
                "total_points": h.get("total_points", 0),
                "overall_rank": h.get("overall_rank"),
                "team_value": round((h.get("value") or 0) / 10, 1),
                "bank": round((h.get("bank") or 0) / 10, 1),
                "transfers": h.get("event_transfers", 0),
                "transfer_cost": h.get("event_transfers_cost", 0),
                "captain_player": c.get("captain_player"),
                "captain_raw_points": c.get("captain_raw_points", 0),
                "captain_multiplier": c.get("captain_multiplier", 0),
                "captain_points": c.get("captain_points", 0),
            })
    # League ranks per GW, with overall rank as stable tie-breaker.
    by_gw = defaultdict(list)
    for r in raw:
        by_gw[r["gw"]].append(r)
    previous_ranks = {}
    for gw in range(1, latest_gw + 1):
        rows = by_gw.get(gw, [])
        rows.sort(key=lambda x: (-x["total_points"], x.get("overall_rank") or 10**15, x["manager_name"]))
        for idx, r in enumerate(rows, start=1):
            r["league_rank"] = idx
            prev = previous_ranks.get(r["manager_id"])
            r["previous_rank"] = prev
            r["rank_change"] = None if prev is None else prev - idx
            previous_ranks[r["manager_id"]] = idx
    return raw


def add_cumulative_metrics(rows, latest_gw):
    by_mid = defaultdict(list)
    by_gw = defaultdict(list)
    for r in rows:
        by_mid[r["manager_id"]].append(r)
        by_gw[r["gw"]].append(r)

    # Weekly MVP flag, shared wins count as 1 win each per the supplied rule.
    for gw, group in by_gw.items():
        if not group:
            continue
        top = max(x["gw_points"] for x in group)
        for x in group:
            x["gw_mvp_win"] = 1 if x["gw_points"] == top else 0

    for mid, group in by_mid.items():
        group.sort(key=lambda x: x["gw"])
        best_points = -1
        best_gw = None
        captain_total = 0
        mvp_total = 0
        for x in group:
            captain_total += x["captain_points"]
            mvp_total += x.get("gw_mvp_win", 0)
            if x["gw_points"] > best_points:
                best_points = x["gw_points"]
                best_gw = x["gw"]
            x["captain_points_cumulative"] = captain_total
            x["gw_mvp_wins_cumulative"] = mvp_total
            x["best_gw_points"] = best_points
            x["best_gw_number"] = best_gw


def penalty_projection_for_period(period, rows, through_gw, finalized=False):
    if not CONFIG.get("penalty_system", {}).get("enabled"):
        return {"status": "disabled"}
    if period.get("penalty_teams") is None:
        return {
            "status": "not_configured",
            "month": period["month"],
            "year": period["year"],
            "start_gw": period["start_gw"],
            "end_gw": period["end_gw"],
            "gw_count": period["gw_count"],
            "penalty_pool_thb": period["penalty_pool_thb"],
            "penalty_teams": None,
            "projected": not finalized,
            "reason": f"Penalty-team count for a {period['gw_count']}-GW month is not configured.",
            "entries": [],
        }
    period_rows = [r for r in rows if period["start_gw"] <= r["gw"] <= min(through_gw, period["end_gw"])]
    if not period_rows:
        return {
            "status": "not_started",
            "month": period["month"], "year": period["year"],
            "start_gw": period["start_gw"], "end_gw": period["end_gw"],
            "gw_count": period["gw_count"], "penalty_pool_thb": period["penalty_pool_thb"],
            "penalty_teams": period["penalty_teams"], "entries": [],
        }
    totals = defaultdict(int)
    names = {}
    season_totals = {}
    for r in period_rows:
        totals[r["manager_id"]] += r["gw_points"]
        names[r["manager_id"]] = (r["manager_name"], r["team_name"])
        if r["gw"] == min(through_gw, period["end_gw"]):
            season_totals[r["manager_id"]] = r["total_points"]
    monthly = [{
        "manager_id": mid,
        "manager_name": names[mid][0],
        "team_name": names[mid][1],
        "monthly_points": pts,
        "season_total_points": season_totals.get(mid, 0),
    } for mid, pts in totals.items()]
    monthly.sort(key=lambda x: (-x["monthly_points"], -x["season_total_points"], x["manager_name"]))
    top_score = monthly[0]["monthly_points"]

    # Penalty cutoff tie is intentionally unresolved because no tie rule was supplied.
    n = int(period["penalty_teams"])
    ascending = sorted(monthly, key=lambda x: (x["monthly_points"], x["manager_name"]))
    cutoff_tie = False
    if len(ascending) > n:
        cutoff_score = ascending[n - 1]["monthly_points"]
        same = [x for x in ascending if x["monthly_points"] == cutoff_score]
        inside_same = [x for x in ascending[:n] if x["monthly_points"] == cutoff_score]
        if len(same) > len(inside_same):
            cutoff_tie = True
    if cutoff_tie:
        return {
            "status": "tie_review",
            "month": period["month"], "year": period["year"],
            "start_gw": period["start_gw"], "end_gw": period["end_gw"],
            "gw_count": period["gw_count"], "penalty_pool_thb": period["penalty_pool_thb"],
            "penalty_teams": n, "projected": not finalized,
            "monthly_ranking": monthly,
            "entries": [],
            "reason": "Tie at the penalty cutoff; no penalty-cutoff tie rule is configured.",
        }

    penalized = [dict(x) for x in ascending[:n]]
    for x in penalized:
        x["monthly_penalty_gap"] = max(0, top_score - x["monthly_points"])
    total_gap = sum(x["monthly_penalty_gap"] for x in penalized)
    if total_gap <= 0:
        payments = [0] * len(penalized)
    else:
        raw_pay = [period["penalty_pool_thb"] * x["monthly_penalty_gap"] / total_gap for x in penalized]
        base = [math.floor(x) for x in raw_pay]
        remain = int(period["penalty_pool_thb"] - sum(base))
        order = sorted(range(len(raw_pay)), key=lambda i: raw_pay[i] - base[i], reverse=True)
        for i in order[:remain]:
            base[i] += 1
        payments = base
    for x, pay in zip(penalized, payments):
        x["penalty_thb"] = int(pay)
    penalized.sort(key=lambda x: (-x["penalty_thb"], x["monthly_points"]))
    return {
        "status": "finalized" if finalized else "projected",
        "month": period["month"], "year": period["year"],
        "start_gw": period["start_gw"], "end_gw": period["end_gw"],
        "gw_count": period["gw_count"], "gw_completed": min(through_gw, period["end_gw"]) - period["start_gw"] + 1,
        "penalty_pool_thb": period["penalty_pool_thb"], "penalty_teams": n,
        "projected": not finalized,
        "top_score": top_score,
        "monthly_ranking": monthly,
        "entries": penalized,
    }


def build_penalty_history(rows, latest_gw):
    periods = []
    finalized_total_by_manager = defaultdict(int)
    finalized_times_by_manager = defaultdict(int)
    collected = 0
    for period in CONFIG.get("penalty_system", {}).get("schedule", []):
        if latest_gw < period["start_gw"]:
            result = {
                "status": "not_started", "month": period["month"], "year": period["year"],
                "start_gw": period["start_gw"], "end_gw": period["end_gw"], "gw_count": period["gw_count"],
                "penalty_pool_thb": period["penalty_pool_thb"], "penalty_teams": period.get("penalty_teams"), "entries": []
            }
        elif latest_gw >= period["end_gw"]:
            result = penalty_projection_for_period(period, rows, period["end_gw"], finalized=True)
        else:
            result = penalty_projection_for_period(period, rows, latest_gw, finalized=False)
        periods.append(result)
        if result.get("status") == "finalized":
            collected += result.get("penalty_pool_thb", 0)
            for x in result.get("entries", []):
                finalized_total_by_manager[x["manager_id"]] += x["penalty_thb"]
                if x["penalty_thb"] > 0:
                    finalized_times_by_manager[x["manager_id"]] += 1
    return periods, dict(finalized_total_by_manager), dict(finalized_times_by_manager), collected


def ranking_for_metric(rows_at_gw, metric):
    if metric == "season_rank":
        return sorted(rows_at_gw, key=lambda x: (x["league_rank"], x["manager_name"]))
    if metric == "gw_mvp_wins":
        return sorted(rows_at_gw, key=lambda x: (-x["gw_mvp_wins_cumulative"], -x["total_points"], -x["best_gw_points"], x["manager_name"]))
    if metric == "team_value":
        return sorted(rows_at_gw, key=lambda x: (-x["team_value"], x["manager_name"]))
    if metric == "captain_points":
        return sorted(rows_at_gw, key=lambda x: (-x["captain_points_cumulative"], x["manager_name"]))
    return []


def metric_value(row, metric):
    if metric == "season_rank": return row["total_points"]
    if metric == "gw_mvp_wins": return row["gw_mvp_wins_cumulative"]
    if metric == "team_value": return row["team_value"]
    if metric == "captain_points": return row["captain_points_cumulative"]
    return None


def reward_candidates(prize, rows_at_gw):
    ranking = ranking_for_metric(rows_at_gw, prize["metric"])
    if prize["metric"] == "season_rank":
        start = int(prize.get("target_rank", 1)) - 1
        ranking = ranking[start: start + 2]
    else:
        ranking = ranking[:2]
    return [{
        "manager_id": r["manager_id"],
        "manager_name": r["manager_name"],
        "team_name": r["team_name"],
        "value": metric_value(r, prize["metric"]),
        "league_rank": r["league_rank"],
        "best_gw_points": r["best_gw_points"],
        "total_points": r["total_points"],
    } for r in ranking]


def top_tie(prize, candidates):
    if prize["metric"] == "season_rank" or len(candidates) < 2:
        return False
    if candidates[0]["value"] != candidates[1]["value"]:
        return False
    # Weekly MVP has explicit tie breakers in the supplied rules.
    if prize["metric"] == "gw_mvp_wins":
        for field in ("total_points", "best_gw_points"):
            if candidates[0][field] != candidates[1][field]:
                return False
    return True


def allocate_rewards(rows_at_gw):
    system = CONFIG.get("prize_system", {})
    if not system.get("enabled"):
        return []
    max_prizes = int(system.get("max_prizes_per_manager") or 0)
    pass_rank = int(system.get("pass_down_max_category_rank") or 1)
    rewards = []
    for p in system.get("prizes", []):
        candidates = reward_candidates(p, rows_at_gw)
        rewards.append({
            "key": p["key"], "label": p["label"], "icon": p.get("icon", "🏅"),
            "amount_thb": p["amount_thb"], "percent": p["percent"], "metric": p["metric"],
            "candidates": candidates, "metric_leader": candidates[0] if candidates else None,
            "nearest_challenger": candidates[1] if len(candidates) > 1 else None,
            "gap": (candidates[0]["value"] - candidates[1]["value"]) if len(candidates) > 1 and p["metric"] != "season_rank" else None,
            "top_tie": top_tie(p, candidates),
            "projected_owner": None, "eligibility_status": "pending", "reason": "",
        })

    # Allocate higher-value groups first. Equal-value over-cap conflicts are left for review.
    counts = defaultdict(int)
    amounts = sorted({r["amount_thb"] for r in rewards}, reverse=True)
    for amount in amounts:
        group = [r for r in rewards if r["amount_thb"] == amount]
        tentative = []
        for r in group:
            if r["top_tie"]:
                r["eligibility_status"] = "tie_review"
                r["reason"] = "Top metric remains tied after configured tie breakers."
                continue
            cands = r["candidates"][:pass_rank]
            if not cands:
                r["eligibility_status"] = "not_available"
                r["reason"] = "No candidate data available."
                continue
            chosen = None
            status = None
            for idx, c in enumerate(cands, start=1):
                if counts[c["manager_id"]] < max_prizes:
                    chosen = c
                    status = "direct" if idx == 1 else "pass_down"
                    break
            if chosen is None:
                r["eligibility_status"] = "unallocated"
                r["reason"] = f"Top {pass_rank} candidates already reached the {max_prizes}-prize cap."
                continue
            tentative.append((r, chosen, status))

        by_manager = defaultdict(list)
        for item in tentative:
            by_manager[item[1]["manager_id"]].append(item)
        conflicted = set()
        for mid, items in by_manager.items():
            capacity = max_prizes - counts[mid]
            if len(items) > capacity:
                for r, _, _ in items:
                    conflicted.add(r["key"])
                    r["eligibility_status"] = "manual_review"
                    r["reason"] = "Equal-value prize conflict: rules say keep the highest-value prizes, but no priority is configured among equal-value prizes."
        for r, chosen, status in tentative:
            if r["key"] in conflicted:
                continue
            r["projected_owner"] = chosen
            r["eligibility_status"] = status
            r["reason"] = "Metric leader is eligible." if status == "direct" else "Prize passes to category #2 because the metric leader already reached the prize cap."
            counts[chosen["manager_id"]] += 1

    for r in rewards:
        r["metric_leader_prize_count"] = counts.get((r["metric_leader"] or {}).get("manager_id"), 0)
    return rewards


def snapshot_for_gw(gw, rows, finalized_penalty_totals_by_manager, finalized_times_by_manager):
    current = [r for r in rows if r["gw"] == gw]
    current.sort(key=lambda x: x["league_rank"])
    rewards = allocate_rewards(current)
    owner_counts = defaultdict(int)
    for r in rewards:
        if r.get("projected_owner"):
            owner_counts[r["projected_owner"]["manager_id"]] += 1
    for r in current:
        r["prize_count"] = owner_counts.get(r["manager_id"], 0)
        r["prize_eligibility"] = "cap_reached" if r["prize_count"] >= CONFIG["prize_system"]["max_prizes_per_manager"] else "eligible"
        r["total_penalty"] = finalized_penalty_totals_by_manager.get(r["manager_id"], 0)
        r["times_penalized"] = finalized_times_by_manager.get(r["manager_id"], 0)
    period = period_for_gw(gw)
    current_penalty = penalty_projection_for_period(period, rows, gw, finalized=False) if period else None
    return {"gw": gw, "standings": current, "rewards": rewards, "current_penalty": current_penalty}


def enrich_monthly_fields(rows, penalty_periods, latest_gw):
    # Finalized cumulative penalty history by end-GW.
    final_events = []
    for p in penalty_periods:
        if p.get("status") == "finalized":
            final_events.append((p["end_gw"], p))
    for row in rows:
        period = period_for_gw(row["gw"])
        row["monthly_points"] = None
        row["monthly_penalty_gap"] = None
        row["monthly_penalty"] = 0
        if period:
            projection = penalty_projection_for_period(period, rows, row["gw"], finalized=(row["gw"] >= period["end_gw"]))
            monthly_row = next((x for x in projection.get("monthly_ranking", []) if x["manager_id"] == row["manager_id"]), None)
            if monthly_row:
                row["monthly_points"] = monthly_row["monthly_points"]
            penalty_row = next((x for x in projection.get("entries", []) if x["manager_id"] == row["manager_id"]), None)
            if penalty_row:
                row["monthly_penalty_gap"] = penalty_row.get("monthly_penalty_gap")
                row["monthly_penalty"] = penalty_row.get("penalty_thb", 0)
        total = 0
        times = 0
        for end_gw, p in final_events:
            if end_gw <= row["gw"]:
                x = next((e for e in p.get("entries", []) if e["manager_id"] == row["manager_id"]), None)
                if x:
                    total += x.get("penalty_thb", 0)
                    if x.get("penalty_thb", 0) > 0:
                        times += 1
        row["total_penalty"] = total
        row["times_penalized"] = times


def validate(config, managers, rows, latest_gw, snapshots, penalty_periods):
    warnings = []
    def add(level, code, message):
        warnings.append({"level": level, "code": code, "message": message})

    if not managers:
        add("error", "NO_MANAGERS", "No league managers were returned by the FPL API.")
    ids = [m["manager_id"] for m in managers]
    if len(ids) != len(set(ids)):
        add("error", "DUPLICATE_MANAGERS", "Duplicate manager IDs were returned by league standings.")

    expected_keys = {(m["manager_id"], gw) for m in managers for gw in range(1, latest_gw + 1)}
    actual_keys = [(r["manager_id"], r["gw"]) for r in rows]
    if len(actual_keys) != len(set(actual_keys)):
        add("error", "DUPLICATE_MANAGER_GW", "Duplicate Manager × Gameweek rows detected.")
    missing = sorted(expected_keys - set(actual_keys))
    if missing:
        add("warning", "MISSING_GAMEWEEKS", f"{len(missing)} Manager × Gameweek rows are missing from FPL history.")

    penalty = config.get("penalty_system", {})
    if penalty.get("enabled"):
        total_gws = sum(p["gw_count"] for p in penalty.get("schedule", []))
        if total_gws != 38:
            add("error", "PENALTY_GW_RANGE", f"Penalty schedule covers {total_gws} GWs instead of 38.")
        for p in penalty.get("schedule", []):
            if p.get("penalty_teams") is None:
                add("warning", "PENALTY_TEAMS_NOT_CONFIGURED", f"{p['month']} {p['year']} has {p['gw_count']} GWs, but the number of Noop teams for a {p['gw_count']}-GW month is not configured. Penalty projection/finalization is disabled for that period.")
        pools = sum(p["penalty_pool_thb"] for p in penalty.get("schedule", []))
        target = penalty.get("season_target_thb") or 0
        if pools != target:
            add("warning", "PENALTY_ROUNDING_VARIANCE", f"Rounded monthly penalty pools total {pools} THB versus the {target} THB season target ({pools-target:+g} THB). No automatic adjustment was made.")

    prizes = config.get("prize_system", {})
    if prizes.get("enabled"):
        amount_total = sum(p["amount_thb"] for p in prizes.get("prizes", []))
        pct_total = sum(p["percent"] for p in prizes.get("prizes", []))
        target = prizes.get("season_target_thb") or 0
        if abs(amount_total - target) > 0.001:
            add("error", "PRIZE_AMOUNT_TOTAL", f"Prize amounts total {amount_total} THB but target is {target} THB.")
        if abs(pct_total - 100) > 0.001:
            add("error", "PRIZE_PERCENT_TOTAL", f"Prize percentages total {pct_total}% instead of 100%.")

    latest_snapshot = snapshots.get(str(latest_gw), {})
    for r in latest_snapshot.get("rewards", []):
        if r.get("eligibility_status") in {"tie_review", "manual_review"}:
            add("warning", "PRIZE_REVIEW_REQUIRED", f"{r['label']}: {r['reason']}")
    for p in penalty_periods:
        if p.get("status") == "tie_review":
            add("warning", "PENALTY_TIE_REVIEW", f"{p['month']} {p['year']}: {p['reason']}")
    return warnings


def write_js(payload):
    DATA_FILE.write_text("window.FPL_DASHBOARD_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def error_payload(message):
    return {
        "status": "error",
        "league": CONFIG.get("league", {}),
        "config": CONFIG,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "error": message,
    }


def main():
    print("=" * 70)
    print(f"SMT NPI FPL Dashboard updater — League {LEAGUE_ID}")
    print("=" * 70)
    try:
        _, player_names, latest_gw = get_bootstrap()
        if latest_gw <= 0:
            raise RuntimeError("No completed Gameweek is available yet.")
        league_meta, managers = get_league_managers()
        histories = get_histories(managers, latest_gw)
        captain_rows = get_captain_rows(managers, player_names, latest_gw)
        rows = compute_base_rows(managers, histories, captain_rows, latest_gw)
        add_cumulative_metrics(rows, latest_gw)
        penalty_periods, final_penalty_by_manager, times_by_manager, collected = build_penalty_history(rows, latest_gw)
        enrich_monthly_fields(rows, penalty_periods, latest_gw)

        snapshots = {}
        for gw in range(1, latest_gw + 1):
            # Historical snapshot needs finalized penalties only through that GW.
            hist_totals = defaultdict(int)
            hist_times = defaultdict(int)
            for p in penalty_periods:
                if p.get("status") == "finalized" and p.get("end_gw", 99) <= gw:
                    for x in p.get("entries", []):
                        hist_totals[x["manager_id"]] += x.get("penalty_thb", 0)
                        if x.get("penalty_thb", 0) > 0:
                            hist_times[x["manager_id"]] += 1
            snapshots[str(gw)] = snapshot_for_gw(gw, rows, hist_totals, hist_times)

        audits = validate(CONFIG, managers, rows, latest_gw, snapshots, penalty_periods)
        prize_target = CONFIG.get("prize_system", {}).get("season_target_thb", 0)
        penalty_target = CONFIG.get("penalty_system", {}).get("season_target_thb", 0)
        current_period = next((p for p in penalty_periods if p.get("start_gw", 999) <= latest_gw <= p.get("end_gw", -1)), None)
        projected_this_month = current_period.get("penalty_pool_thb", 0) if current_period and current_period.get("status") == "projected" else 0

        payload = {
            "status": "ok",
            "league": {
                "league_id": LEAGUE_ID,
                "league_name": league_meta.get("name") or CONFIG["league"]["display_name"],
                "display_name": CONFIG["league"]["display_name"],
                "season": CONFIG["league"]["season"],
                "manager_count": len(managers),
            },
            "latest_gw": latest_gw,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "master_rows": sorted(rows, key=lambda x: (x["gw"], x["league_rank"])),
            "snapshots": snapshots,
            "penalty_periods": penalty_periods,
            "financial": {
                "collected_penalty_thb": collected,
                "projected_current_period_thb": projected_this_month,
                "season_target_thb": penalty_target,
                "remaining_thb": max(0, penalty_target - collected),
                "rounded_schedule_total_thb": sum(p.get("penalty_pool_thb", 0) for p in CONFIG.get("penalty_system", {}).get("schedule", [])),
                "prize_target_thb": prize_target,
            },
            "penalty_ledger": [{
                "manager_id": m["manager_id"],
                "manager_name": m["manager_name"],
                "team_name": m["team_name"],
                "times_penalized": times_by_manager.get(m["manager_id"], 0),
                "total_penalty_paid_thb": final_penalty_by_manager.get(m["manager_id"], 0),
            } for m in managers],
            "audit": audits,
            "config_summary": CONFIG,
        }
        write_js(payload)
        print(f"SUCCESS: GW{latest_gw} data written to {DATA_FILE.name}")
        return 0
    except Exception as exc:
        write_js(error_payload(str(exc)))
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
