# smt-npi-fpl-dashboard — FPL season dashboard

League ID: **754393** (preserved from this repository). Earlier project notes reverse these IDs; verify the league name before changing this setting.

## Files

- `rules_config.json`: this league's independent prize rules, monthly schedule and penalties.
- `dashboard_data.js`: last successful FPL snapshot; future updates retain `history` and `captain_history`.
- `engine.js`: browser calculation engine; penalty tie sharing, prize eligibility and validation.
- `app.js`, `styles.css`, `index.html`: rendering, controls and responsive layout.
- `payments.json`: explicitly recorded penalty payments and finalized prize awards.
- `fpl_dashboard_updater.py`: manual Python standard-library updater.
- `tests/engine.test.js`: calculation regression checks.

## Weekly update on your Mac

Open Terminal in your repository folder:

```bash
git switch main
git pull --ff-only origin main
python3 fpl_dashboard_updater.py
node tests/engine.test.js # optional if Node.js is installed
git status
git add dashboard_data.js
git commit -m "Update FPL Gameweek data"
git push origin main
```

Or double-click `update_and_publish.command`. It refuses uncommitted edits and publishes only the data file. No scheduled FPL fetching has been added. Existing Pages deployment runs after a main-branch push.

Preview locally using `python3 -m http.server 8000` and open http://localhost:8000. Opening index.html directly cannot fetch JSON files.

## Payments

No historic payment receipt records were supplied. Previous fields called collected/paid were actually assessments. The new dashboard uses only payments.json as evidence of payment. To record a verified payment, add an object to `penalties`:

```json
{"manager_id": 123456, "month": "Aug", "year": 2026, "amount_thb": 50, "date": "2026-10-04"}
```

For a confirmed prize award, use `prizes` with manager_id, amount_thb, key, date and `"status": "finalized"`. Never record a projected award as finalized. Review and commit ledger edits separately.

## Rule changes

Review this league's rules_config.json only. Current instruction changes penalty cutoff ties to shared occupied-slot amounts and prize pass-down to continue through all eligible managers. The underlying gap-weighted penalty formula and each league's prize amounts remain intact. Unconfigured prize ties stay pending; SMT equal-value conflicts remain manual review.

Penalty precision is retained for equal division. Display rounds to two decimals; an indivisible satang needs an explicit settlement policy. The configured season pool variance is displayed rather than silently adjusted.

## GitHub Pages

The existing `.github/workflows/pages.yml` publishes static files after a push to main. Keep Settings → Pages → Source set to GitHub Actions. All assets use relative paths and work under the repository subdirectory. No build step or backend is required.

## Troubleshooting

- API timeout: the existing snapshot stays intact. Retry later.
- Missing GW: updater rejects incomplete manager history and preserves previous data.
- Missing captain data: the dashboard flags the captain prize for review.
- Old saved snapshot: a data warning identifies age and missing historical detail. Future updater runs preserve full history.
- Zero recorded funding: no payment records are loaded; assessed amounts are separate.
- `DATA WARNING`: open the warning panel and inspect the affected rules/data before settling money.
- No automatic fetching: run the manual updater each GW.

## Verification

Run `node tests/engine.test.js` and `python3 -m unittest discover -s tests -p '*_test.py'`. Calculation checks cover ranking, transfer hits, penalty boundary ties, multiple ties, money conservation, prize caps/pass-down, missing GWs, month transitions, and financial totals.
