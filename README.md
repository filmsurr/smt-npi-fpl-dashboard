# SMT NPI FPL Dashboard — League 754393

A static, shareable Fantasy Premier League dashboard built for **League 754393**. The dashboard uses the official public FPL API, a Python updater, and a static `dashboard_data.js` file so it can be hosted on GitHub Pages.

## What is included

- Glassmorphism desktop / tablet / mobile dashboard
- Automatic manager discovery from the FPL league ID
- One **Manager × Gameweek** master dataset
- Top 3 hero cards with rank movement, GW score and gaps
- Configured special competitions only:
  - Most Weekly MVPs
  - Highest Team Value
  - Total Captain Points
- Metric Leader vs Projected Prize Owner
- Maximum 2 prizes per manager
- Pass-down limited to category #2
- Monthly penalty projection vs finalized penalty
- Total penalty paid and times penalized per manager
- Collected / projected / target / remaining financial KPIs
- GW selector and penalty-period selector
- Compact **Export Latest PNG** share card for LINE / Messenger / WhatsApp / Discord
- Audit warnings for missing data, rule gaps, financial mismatches and unresolved ties
- GitHub Pages workflow
- Beginner-friendly macOS setup and weekly publishing commands

## League rules encoded

### Prize system

| Prize | Share | Amount |
|---|---:|---:|
| League Champion | 35% | 962.5 THB |
| Runner-Up | 20% | 550 THB |
| 3rd Place | 15% | 412.5 THB |
| Most Weekly MVPs | 10% | 275 THB |
| Highest Team Value | 10% | 275 THB |
| Total Captain Points | 10% | 275 THB |

Each manager may receive at most **2 prizes**. The supplied rule says to retain the highest-value prizes first. If a prize needs to pass down, it can go only to category #2.

The three special prizes are all worth 275 THB. If an equal-value conflict would force the dashboard to choose which one a manager keeps, the dashboard shows **Review required** because no priority among those equal-value prizes was supplied.

### Weekly MVP tie-breakers

If managers have the same number of Weekly MVP wins, the supplied rule uses:

1. higher season total points
2. higher best single-GW score

### Penalty pool formula

Monthly pool:

`2,750 THB × (Gameweeks in month / 38)`

Rounded to the nearest whole THB.

| Month | GWs | Count | Pool | Noop teams |
|---|---|---:|---:|---:|
| Aug 2026 | GW1–GW2 | 2 | 145 THB | **Not configured** |
| Sep 2026 | GW3–GW5 | 3 | 217 THB | 2 |
| Oct 2026 | GW6–GW9 | 4 | 289 THB | 2 |
| Nov 2026 | GW10–GW12 | 3 | 217 THB | 2 |
| Dec 2026 | GW13–GW18 | 6 | 434 THB | 3 |
| Jan 2027 | GW19–GW23 | 5 | 362 THB | 3 |
| Feb 2027 | GW24–GW27 | 4 | 289 THB | 2 |
| Mar 2027 | GW28–GW30 | 3 | 217 THB | 2 |
| Apr 2027 | GW31–GW33 | 3 | 217 THB | 2 |
| May 2027 | GW34–GW38 | 5 | 362 THB | 3 |

### Important audit warning

The supplied rules define Noop-team counts for 3, 4, 5 and 6-GW months, but **do not define the number of Noop teams for a 2-GW month**. Therefore August penalty selection/payment is disabled until this rule is added to `rules_config.json`.

The rounded monthly pools total **2,749 THB**, 1 THB below the 2,750 THB target. The dashboard reports the difference and does not silently modify any month.

## First local test

On macOS:

```bash
python3 fpl_dashboard_updater.py
open index.html
```

The first update downloads all completed historical GW data. Later runs reuse `.fpl_cache` for immutable completed-GW picks/live data.

To force a complete historical refresh:

```bash
python3 fpl_dashboard_updater.py --refresh-all
```

## GitHub Pages — first time

Double-click:

`setup_github.command`

It checks Python, Git, internet access, the Git repository, updates FPL data, commits and pushes the dashboard to:

`https://github.com/filmsurr/smt-npi-fpl-dashboard.git`

The script then opens the repository's **Settings → Pages** page. If needed, choose **GitHub Actions** as the publishing source.

Expected permanent Pages URL:

`https://filmsurr.github.io/smt-npi-fpl-dashboard/`

## Normal update after each Gameweek

Double-click:

`update_and_publish.command`

Workflow:

FPL API → Python updater → `dashboard_data.js` → Git commit → Git push → GitHub Pages redeploy

If there is no changed data, the script stops without creating a commit.

## Exporting a share image

Open the dashboard and click:

**⬇ Export Latest PNG**

This exports a compact 1080px share card instead of the entire long webpage. It includes:

- League name and GW
- Top 3
- Special competition leaders
- Current penalty risk
- Collected penalty / target
- Projected prize owners
- Updated time

Filename format:

`{LEAGUE_NAME}_GW{GW}_{DATE}.png`

## Files

- `index.html` — visualization, interactions and PNG export only
- `dashboard_data.js` — generated static data
- `fpl_dashboard_updater.py` — FPL API + calculations + validation
- `rules_config.json` — **single source of truth for league rules**
- `setup_github.command` — first GitHub setup/publish
- `update_and_publish.command` — normal weekly update/publish
- `.github/workflows/pages.yml` — GitHub Pages deployment
- `.gitignore` — cache/system exclusions
