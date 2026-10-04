# Dashboard audit and implementation review

## Phase 1 — Repository audit
Existing static HTML with inline CSS/rendering, rules_config.json, Python updater, dashboard_data.js, manual Mac scripts and Pages deployment. Retained repository structure, configuration, historical snapshot and Pages workflow. No scheduled FPL updater introduced.

## Phase 2 — Logic audit
Monthly points use cumulative total_points deltas, avoiding duplicate transfer deductions. Penalty pool shares are weighted by distance from the monthly leader. BANZAI broke penalty cutoff ties by name; SMT withheld ties. Prior finalized assessments were labelled paid/collected without receipts. SMT inline prize amount fallbacks disagreed with JSON rules. Prize cap/pass-down logic was duplicated and limited to two candidates. Saved GW5 snapshots omit full GW history; SMT also omits full monthly rankings. Repository league IDs differ from earlier conversation notes; preserved and flagged.

## Phase 3 — Architecture
rules_config.json + dashboard_data.js + payments.json → engine.js → app.js → index.html/styles.css. Python updater retains raw GW and captain history for future independent verification. Legacy aggregate fields remain assessments and are labelled as such.

## Phase 4 — Wireframe
Desktop: compact header/navigation; four snapshot columns; monthly ranking (two-thirds) and command summary (one-third); three-column prize race; expandable monthly tracker; financial table; compact expandable manager rows; filtered history; collapsible rules.
Mobile: compact stacked header; two snapshot columns with full-width first place and funding; current month stack; one-column prize race at narrow widths; important table columns stay visible and supporting fields expand inside rows.

## Phase 5 — UX
Eligible prize winner is primary. All categories stay visible. Financial labels separate recorded, assessed and projected amounts. Status labels accompany colors. Controls target 44px. Warnings are visible rather than silently suppressing gaps. Export summary uses a native canvas without an external dependency.

## Phase 6 — Calculations
Penalty tied groups share all occupied slot money. Full precision keeps equal ties and money conservation; display rounds to two decimals. Unconfigured indivisible-satang settlement remains explicit. Prize pass-down continues through all eligible managers per current instruction; only configured prize tiebreaks are used. SMT equal-value conflicts remain manual review. Finance uses explicit transactions only.

## Phase 7 — Implementation
Separated engine/rendering/styles. Preserved snapshot bytes. Updater requires checked final events, validates complete manager histories, prevents GW regression/history loss, writes atomically, and retains raw history. Manual publish refuses dirty worktrees and stages data only.

## Phase 8 — Testing
14 Node regression checks plus 5 Python updater tests per repository. JavaScript/Python/shell syntax and relative Pages asset loading checked. Real browser responsive review was attempted but the browser download failed in this environment. Live FPL API request timed out. These two checks remain blocked; do not represent them as passed.

## Phase 9 — GitHub preparation
Separate astra-dashboard-redesign branch per repository. No snapshot refresh, payment fabrication, league-ID reassignment or automatic-fetch workflow. Major redesign stays on branches until browser and live API verification are complete.

## Phase 10 — Change summary
UI: compact sports analytics layout and all prize categories.
DATA: raw history retained for future runs, visible completeness warnings.
PRIZE LOGIC: config-driven cap, pass-down, pending unconfigured ties.
PENALTY LOGIC: occupied-slot sharing and money conservation in browser and updater.
FPL API: data_checked requirement, history validation and atomic snapshot preservation.
RESPONSIVE DESIGN: narrow-screen columns and expandable supporting detail; real-browser check pending.
BUG FIXES: removes JSON/inline prize disagreement and false payment labels.
GITHUB: isolated review branches, existing Pages workflow retained.

## Phase 11 — GitHub update
Prepared for branch publication and pull request review. Main and the currently published site remain unchanged until verification permits merging.
