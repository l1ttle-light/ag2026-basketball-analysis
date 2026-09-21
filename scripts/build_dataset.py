import glob
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(os.environ.get("AG2026_DATA_DIR", "data"))
GAMES_DIR = ROOT / "raw" / "games"
OUTPUT_FILE = ROOT / "processed" / "prepared.json"
TARGETS = ["CHN", "JPN", "KOR", "IRI"]
TEAM_NAMES = {
    "CHN": "中国",
    "JPN": "日本",
    "KOR": "韩国",
    "IRI": "伊朗",
}
SHOT_ACTIONS = {"P2I", "P2O", "P2F", "P3", "P3F"}
FAST_ACTIONS = {"P2F", "P3F"}


def num(stats, key):
    raw = stats.get(key, "") if stats else ""
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0


def clock_seconds(raw):
    if raw in (None, ""):
        return None
    text = str(raw).strip()
    try:
        if ":" in text:
            mins, secs = text.split(":", 1)
            return float(mins) * 60 + float(secs)
        return float(text)
    except ValueError:
        return None


def member_ext(member, code):
    for item in member.get("Extensions", []):
        if item.get("Code") == code:
            return item.get("Value", "")
    return ""


def stage_name(info):
    key = info["Key"]
    if ".SFNL." in key:
        return "半决赛"
    if ".QFNL." in key:
        return "四分之一决赛"
    if ".FNL-.000200--" in key:
        return "三四名决赛"
    if ".FNL-.000100--" in key:
        return "决赛"
    return "小组赛"


def team_from_action(action, home_org, away_org):
    team = action.get("Team")
    if team == "H":
        return home_org
    if team == "A":
        return away_org
    comps = action.get("Competitors") or []
    return comps[0].get("Org", "") if comps else ""


def estimate_fastbreak(actions, home_org, away_org):
    """Approximate transition possessions from public play-by-play.

    A possession is tagged as transition when the first shot, turnover, or free
    throw occurs no more than seven seconds after a defensive rebound or an
    opponent turnover. Official P2F/P3F makes are always included. This is an
    intentionally reproducible approximation, not video coding.
    """

    rows = []
    for idx, action in enumerate(actions):
        period = int(action.get("Period") or 0)
        secs = clock_seconds(action.get("TimeStamp"))
        org = team_from_action(action, home_org, away_org)
        rows.append((idx, action, period, secs, org))

    counts = Counter()
    points = Counter()
    counted_events = set()
    counted_windows = defaultdict(list)

    for pos, (idx, action, period, secs, org) in enumerate(rows):
        if secs is None or period <= 0:
            continue

        gain_org = None
        if action.get("Action") == "REB" and action.get("Result") == "DR":
            gain_org = org
        elif action.get("Action") in {"TO", "TTO"} and org in {home_org, away_org}:
            gain_org = away_org if org == home_org else home_org

        if not gain_org:
            continue

        for nxt_idx, nxt, nxt_period, nxt_secs, nxt_org in rows[pos + 1 :]:
            if nxt_period != period:
                break
            if nxt_secs is None:
                continue
            dt = secs - nxt_secs
            if dt < -0.2:
                continue
            if dt > 12:
                break

            terminal = nxt.get("Action") in SHOT_ACTIONS or nxt.get("Action") in {"TO", "TTO", "FT"}
            if not terminal:
                continue
            if nxt_org != gain_org:
                break

            is_fast = dt <= 7.0 or nxt.get("Action") in FAST_ACTIONS
            if is_fast:
                counts[gain_org] += 1
                counted_events.add(nxt_idx)
                counted_windows[gain_org].append((period, secs))
                if nxt.get("Action") in SHOT_ACTIONS and nxt.get("Result") == "MADE":
                    points[gain_org] += 3 if nxt.get("Action") in {"P3", "P3F"} else 2
                elif nxt.get("Action") == "FT":
                    # Include the immediate free-throw sequence caused by the
                    # transition attack. The official feed keeps these at the
                    # same game-clock timestamp.
                    for _, ft, ft_period, ft_secs, ft_org in rows[pos + 1 :]:
                        if ft_period != period or ft_org != gain_org or ft.get("Action") != "FT":
                            if ft.get("Action") not in {"FOUL", "FD"}:
                                break
                            continue
                        if abs((ft_secs or 0) - (nxt_secs or 0)) > 0.2:
                            break
                        if ft.get("Result") == "MADE":
                            points[gain_org] += 1
            break

    # Ensure every official made fast-break basket is represented, but avoid
    # adding a second possession for a put-back inside an already counted break.
    for idx, action, period, secs, org in rows:
        if action.get("Action") not in FAST_ACTIONS or action.get("Result") != "MADE":
            continue
        if idx in counted_events:
            continue
        near_counted = any(p == period and secs is not None and 0 <= start - secs <= 15 for p, start in counted_windows[org])
        shot_points = 3 if action.get("Action") == "P3F" else 2
        if idx not in counted_events:
            points[org] += shot_points
        if not near_counted:
            counts[org] += 1
            if secs is not None:
                counted_windows[org].append((period, secs))
    return counts, points


def read_game(result_file):
    result = json.loads(result_file.read_text())
    action_file = Path(str(result_file).replace(".result.json", ".actions.json"))
    actions = json.loads(action_file.read_text())
    info = result["Info"]
    competitors = result["Competitors"]
    home, away = competitors[0], competitors[1]
    return result, actions, info, home, away


games = []
team_games = []
player_games = []
pbp_rows = []
raw_files = []

for result_path in sorted(GAMES_DIR.glob("*.result.json")):
    result, actions, info, home, away = read_game(result_path)
    involved = {home["Org"], away["Org"]} & set(TARGETS)
    if not involved:
        continue

    action_path = Path(str(result_path).replace(".result.json", ".actions.json"))
    raw_files.extend([str(result_path), str(action_path)])
    game_key = info["Key"]
    date = info["DateTimeRaw"][:10]
    stage = stage_name(info)
    home_score = int(home.get("Result") or 0)
    away_score = int(away.get("Result") or 0)
    official_summary = result.get("Results", {}).get("Result", "")
    data_issue = ""
    if official_summary and official_summary != f"{home_score}-{away_score}":
        data_issue = f"顶层比分字段为{official_summary}，球队分项/逐事件为{home_score}-{away_score}"

    games.append({
        "game_key": game_key,
        "game_no": info.get("UnitNum", ""),
        "date": date,
        "stage": stage,
        "phase": info.get("PhaseDesc", ""),
        "home_org": home["Org"],
        "home_team": TEAM_NAMES.get(home["Org"], home.get("Name", home["Org"])),
        "away_org": away["Org"],
        "away_team": TEAM_NAMES.get(away["Org"], away.get("Name", away["Org"])),
        "home_score": home_score,
        "away_score": away_score,
        "official_summary": official_summary,
        "data_issue": data_issue,
        "event_count": len(actions),
    })

    fast_poss, fast_pts_est = estimate_fastbreak(actions, home["Org"], away["Org"])
    fast_pts_official = Counter()
    for action in actions:
        org = team_from_action(action, home["Org"], away["Org"])
        if action.get("Result") == "MADE" and action.get("Action") == "P2F":
            fast_pts_official[org] += 2
        elif action.get("Result") == "MADE" and action.get("Action") == "P3F":
            fast_pts_official[org] += 3

    for team_obj, opp_obj, venue_side in [(home, away, "主队"), (away, home, "客队")]:
        org = team_obj["Org"]
        if org not in TARGETS:
            continue
        stats = team_obj.get("Stats", {})
        fgm = num(stats, "ST_FIELD_GL_MADE")
        fga = num(stats, "ST_FIELD_GL_ATTEMPT")
        two_m = num(stats, "ST_2PTS_MADE")
        two_a = num(stats, "ST_2PTS_ATTEMPT")
        three_m = num(stats, "ST_3PTS_MADE")
        three_a = num(stats, "ST_3PTS_ATTEMPT")
        ftm = num(stats, "ST_FREE_TH_MADE")
        fta = num(stats, "ST_FREE_TH_ATTEMPT")
        orb = num(stats, "ST_OFF_REBOUND")
        drb = num(stats, "ST_DEF_REBOUND")
        tov = num(stats, "ST_TURNOVER")
        pts = int(team_obj.get("Result") or num(stats, "ST_TOTAL_POINTS"))
        poss = fga - orb + tov + 0.44 * fta
        fb_poss = min(float(fast_poss[org]), poss) if poss > 0 else 0
        fb_points = min(int(fast_pts_est[org]), pts)
        fb_points_official = min(int(fast_pts_official[org]), pts)
        hc_poss = max(poss - fb_poss, 0)
        hc_points = max(pts - fb_points, 0)

        team_games.append({
            "game_key": game_key,
            "game_no": info.get("UnitNum", ""),
            "date": date,
            "stage": stage,
            "team_org": org,
            "team": TEAM_NAMES[org],
            "opponent_org": opp_obj["Org"],
            "opponent": TEAM_NAMES.get(opp_obj["Org"], opp_obj.get("Name", opp_obj["Org"])),
            "venue_side": venue_side,
            "points": pts,
            "opp_points": int(opp_obj.get("Result") or 0),
            "result": "胜" if pts > int(opp_obj.get("Result") or 0) else "负",
            "fgm": fgm,
            "fga": fga,
            "fg_pct": fgm / fga if fga else None,
            "two_m": two_m,
            "two_a": two_a,
            "two_pct": two_m / two_a if two_a else None,
            "three_m": three_m,
            "three_a": three_a,
            "three_pct": three_m / three_a if three_a else None,
            "three_pts_per_att": 3 * three_m / three_a if three_a else None,
            "ftm": ftm,
            "fta": fta,
            "ft_pct": ftm / fta if fta else None,
            "orb": orb,
            "drb": drb,
            "reb": num(stats, "ST_TOTAL_REBOUNDS"),
            "assists": num(stats, "ST_ASSIST"),
            "turnovers": tov,
            "steals": num(stats, "ST_STEAL"),
            "blocks": num(stats, "ST_BLOCKED_SHOT"),
            "fouls": num(stats, "ST_FOUL"),
            "poss_est": poss,
            "overall_ortg_est": 100 * pts / poss if poss else None,
            "fastbreak_points": fb_points,
            "fastbreak_points_official": fb_points_official,
            "fastbreak_poss_est": fb_poss,
            "fastbreak_ortg_est": 100 * fb_points / fb_poss if fb_poss else None,
            "halfcourt_points_est": hc_points,
            "halfcourt_poss_est": hc_poss,
            "halfcourt_ortg_est": 100 * hc_points / hc_poss if hc_poss else None,
            "fastbreak_point_share": fb_points / pts if pts else None,
            "data_issue": data_issue,
        })

        for member in team_obj.get("Members", []):
            s = member.get("Stats", {})
            player_games.append({
                "game_key": game_key,
                "game_no": info.get("UnitNum", ""),
                "date": date,
                "stage": stage,
                "team_org": org,
                "team": TEAM_NAMES[org],
                "opponent": TEAM_NAMES.get(opp_obj["Org"], opp_obj.get("Name", opp_obj["Org"])),
                "bib": member.get("Bib", ""),
                "player": member.get("Name", ""),
                "position": member.get("Position", ""),
                "starter": "否" if member.get("Substitute") else "是",
                "minutes": member_ext(member, "TimeOnCourt"),
                "points": num(s, "ST_TOTAL_POINTS"),
                "fgm": num(s, "ST_FIELD_GL_MADE"),
                "fga": num(s, "ST_FIELD_GL_ATTEMPT"),
                "two_m": num(s, "ST_2PTS_MADE"),
                "two_a": num(s, "ST_2PTS_ATTEMPT"),
                "three_m": num(s, "ST_3PTS_MADE"),
                "three_a": num(s, "ST_3PTS_ATTEMPT"),
                "ftm": num(s, "ST_FREE_TH_MADE"),
                "fta": num(s, "ST_FREE_TH_ATTEMPT"),
                "orb": num(s, "ST_OFF_REBOUND"),
                "drb": num(s, "ST_DEF_REBOUND"),
                "reb": num(s, "ST_TOTAL_REBOUNDS"),
                "assists": num(s, "ST_ASSIST"),
                "turnovers": num(s, "ST_TURNOVER"),
                "steals": num(s, "ST_STEAL"),
                "blocks": num(s, "ST_BLOCKED_SHOT"),
                "fouls": num(s, "ST_FOUL"),
                "plus_minus": num(s, "ST_PLUS_MINUS"),
            })

    for action in actions:
        comps = action.get("Competitors") or []
        pbp_rows.append({
            "game_key": game_key,
            "game_no": info.get("UnitNum", ""),
            "date": date,
            "stage": stage,
            "home_org": home["Org"],
            "away_org": away["Org"],
            "period": int(action.get("Period") or 0),
            "order": int(action.get("Order") or 0),
            "clock": action.get("TimeStamp", ""),
            "team_side": action.get("Team", ""),
            "team_org": team_from_action(action, home["Org"], away["Org"]),
            "action": action.get("Action", ""),
            "action_desc": action.get("ActionDesc", ""),
            "result": action.get("Result", ""),
            "result_desc": action.get("ResultDesc", ""),
            "comment": action.get("Comment", ""),
            "score_home": int(action.get("ScoreH") or 0),
            "score_away": int(action.get("ScoreA") or 0),
            "player": comps[0].get("Name", "") if comps else "",
            "bib": comps[0].get("Bib", "") if comps else "",
            "x": action.get("X", ""),
            "y": action.get("Y", ""),
            "shot_zone": action.get("Line", ""),
        })


summary = []
for org in TARGETS:
    rows = [r for r in team_games if r["team_org"] == org]
    totals = Counter()
    for r in rows:
        for key in [
            "points", "opp_points", "fgm", "fga", "two_m", "two_a",
            "three_m", "three_a", "ftm", "fta", "orb", "drb", "reb",
            "assists", "turnovers", "steals", "blocks", "fouls",
            "poss_est", "fastbreak_points", "fastbreak_poss_est",
            "fastbreak_points_official",
            "halfcourt_points_est", "halfcourt_poss_est",
        ]:
            totals[key] += r[key] or 0
    games_count = len(rows)
    wins = sum(r["result"] == "胜" for r in rows)
    summary.append({
        "team_org": org,
        "team": TEAM_NAMES[org],
        "games": games_count,
        "wins": wins,
        "losses": games_count - wins,
        "points": totals["points"],
        "points_per_game": totals["points"] / games_count if games_count else None,
        "opp_points": totals["opp_points"],
        "margin_per_game": (totals["points"] - totals["opp_points"]) / games_count if games_count else None,
        "fgm": totals["fgm"],
        "fga": totals["fga"],
        "fg_pct": totals["fgm"] / totals["fga"] if totals["fga"] else None,
        "three_m": totals["three_m"],
        "three_a": totals["three_a"],
        "three_pct": totals["three_m"] / totals["three_a"] if totals["three_a"] else None,
        "three_pts_per_att": 3 * totals["three_m"] / totals["three_a"] if totals["three_a"] else None,
        "poss_est": totals["poss_est"],
        "overall_ortg_est": 100 * totals["points"] / totals["poss_est"] if totals["poss_est"] else None,
        "fastbreak_points": totals["fastbreak_points"],
        "fastbreak_points_official": totals["fastbreak_points_official"],
        "fastbreak_poss_est": totals["fastbreak_poss_est"],
        "fastbreak_ortg_est": 100 * totals["fastbreak_points"] / totals["fastbreak_poss_est"] if totals["fastbreak_poss_est"] else None,
        "halfcourt_points_est": totals["halfcourt_points_est"],
        "halfcourt_poss_est": totals["halfcourt_poss_est"],
        "halfcourt_ortg_est": 100 * totals["halfcourt_points_est"] / totals["halfcourt_poss_est"] if totals["halfcourt_poss_est"] else None,
        "fastbreak_point_share": totals["fastbreak_points"] / totals["points"] if totals["points"] else None,
        "orb": totals["orb"],
        "assists": totals["assists"],
        "turnovers": totals["turnovers"],
    })

key_games = [r for r in team_games if r["stage"] in {"半决赛", "三四名决赛", "决赛"}]

assert all(sum(1 for r in team_games if r["team_org"] == org) == 6 for org in TARGETS)
assert len(games) == 19
assert len(key_games) == 8

payload = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "summary": summary,
    "key_games": key_games,
    "team_games": sorted(team_games, key=lambda r: (r["date"], int(r["game_no"] or 0), TARGETS.index(r["team_org"]))),
    "player_games": sorted(player_games, key=lambda r: (r["date"], int(r["game_no"] or 0), r["team_org"], int(r["bib"] or 0))),
    "games": sorted(games, key=lambda r: (r["date"], int(r["game_no"] or 0))),
    "pbp": sorted(pbp_rows, key=lambda r: (r["date"], int(r["game_no"] or 0), r["period"], r["order"])),
    "raw_files": raw_files,
}

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "summary": summary,
    "counts": {
        "games": len(games),
        "team_games": len(team_games),
        "key_games": len(key_games),
        "player_games": len(player_games),
        "pbp": len(pbp_rows),
    },
}, ensure_ascii=False, indent=2))
