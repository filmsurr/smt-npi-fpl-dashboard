# SMT NPI FPL v2.1 — Penalty Fix

This rebuild fixes the current SMT NPI August penalty problem without copying BANZAI prize rules.

Root cause in the previous SMT NPI configuration: the 2-GW penalty-team setting was `null`, so August (2 GWs) could not be finalized/calculated.

Changes:
- 2-GW month configured as 2 penalty teams.
- penalty pools remain based on SMT NPI's 2,750 THB season target.
- monthly penalty score uses official net points after transfer hits.
- Raw Points / Transfer Hits / Penalty Score are shown separately.
- Finalized vs Projected months are explicit.
- season penalty ledger updates finalized payments and times penalized.

To update an existing local GitHub repo, copy these files over your SMT NPI dashboard folder and run `./update_and_publish.command`.
