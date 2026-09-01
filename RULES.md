# SMT NPI FPL — penalty logic v2.1

League ID: **754393**. Prize/penalty season target: **2,750 THB**.

Monthly GW schedule: Aug 2, Sep 3, Oct 4, Nov 3, Dec 6, Jan 5, Feb 4, Mar 3, Apr 3, May 5.

Penalty teams by GW count: 2→2, 3→2, 4→2, 5→3, 6→3.

Monthly pool is `round(2750 × gw_count / 38)`: 2→145, 3→217, 4→289, 5→362, 6→434 THB. Monthly rounded pools total 2,749 THB, so the dashboard shows a -1 THB audit variance rather than silently changing a month.

Monthly penalty score uses **official net FPL points after transfer hits**. The updater calculates each GW's net contribution from the change in `total_points`, while showing `event_transfers_cost` separately. Example: raw 72, hit 4 → net penalty score 68.

Penalty payment is weighted by score gap from the monthly leader. A tied cutoff is marked for manual review.
