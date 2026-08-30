# Changelog

## v2.0

- Rebuilt dashboard architecture around `rules_config.json` as the single source of league rules.
- League managers are auto-detected from FPL League ID 754393.
- Added Manager × Gameweek master data model.
- Added historical league rank / previous rank / rank movement.
- Added captain contribution, Weekly MVP wins, best GW, team value, transfers and penalty fields.
- Added top-3 hero KPI cards and separate current financial KPI.
- Added Metric Leaders / Projected Prizes interaction.
- Added Weekly MVP leaderboard.
- Added projected prize owner logic with 2-prize cap and pass-down limit.
- Added conservative `manual_review` handling for equal-value prize conflicts instead of inventing a priority.
- Added monthly penalty selector, projected/finalized status and season penalty leaderboard.
- Added finalized collected penalty vs projected current-period money.
- Added data/rule audit warnings.
- Added compact 1080px PNG share-card export.
- Added GitHub Pages workflow.
- Added `setup_github.command` and `update_and_publish.command` for macOS.
- Left 2-GW-month Noop team count unconfigured because it is missing from the supplied rules.
