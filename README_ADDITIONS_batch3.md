<!-- Paste into README.md. Do not commit this file. -->

## 1. Module table: add these rows (CI Toolkit section)

| Section | Module | What it does |
|---|---|---|
| CI Toolkit | 8D Tracker | D0 to D8 progress stepper and a planned-versus-actual timeline. Editable step table (status, planned date, completed date, notes) and a "status as of" date. Shows steps done, current step, days open, overdue steps, and flags out-of-order or inconsistent dates. CSV download. |
| CI Toolkit | Kaizen Log | Improvement-idea log scored for impact and effort (1 to 5). Impact/effort matrix with a quick-wins zone set by two thresholds, status funnel (Idea, Plan, Do, Check, Standardized), cumulative estimated savings by date standardized, and a PDCA cycle diagram with live counts. CSV download. |

Sidebar URL paths: `/eight-d` and `/kaizen`. The CI Toolkit section now contains: DMAIC board, FMEA, 5S audit, 5 Why, Fishbone, 8D tracker, Kaizen log.

## 2. Engineering notes: add

**8D tracker**
- The nine steps are fixed (D0 to D8). Steps missing from the table count as Not started; a repeated step uses its last row.
- Overdue = status is not Done and the planned date is before the "status as of" date. Days late = completed minus planned for finished steps (negative = early), or as-of minus planned for overdue steps.
- Days open runs from the opened date to the D8 completion date if D8 is Done, otherwise to the "status as of" date.
- Advisory checks (they do not change the data): a step marked Done while an earlier step is not, Done with no completed date, completion before the opened date, and completion dates out of order.
- Step names follow a common convention; organizations differ, so the names are labels, not a standard.

**Kaizen log**
- Impact and effort are whole numbers from 1 to 5. Quick win = impact at or above the first threshold and effort at or below the second (defaults: impact >= 4, effort <= 2), excluding rejected ideas. "Open" quick wins exclude ideas already standardized.
- The quadrant lines on the matrix follow the two thresholds. Ideas with identical scores are offset slightly so they do not overlap; their position is the score cell, not an exact coordinate.
- Funnel counts ideas that reached at least each stage. Rejected ideas count at the first stage only.
- Cumulative savings adds the estimated annual savings of Standardized ideas, ordered by the date standardized. Standardized ideas with no date or no savings are left out of that chart and the page says how many.

## 3. Limitations: add

- Kaizen savings are annual run-rate estimates entered by the user. They are not audited, not net of implementation cost, and not realized cash.
- The Kaizen matrix scores are the team's judgment on a 1 to 5 scale; the tool does not calculate impact or effort.
- The 8D tracker follows one report through its steps. It does not store the content of the 8D report (containment details, root-cause analysis, team list); use the Notes column for short summaries and the 5 Why and Fishbone tools for the analysis.
- Sample data is simulated for a generic machining and assembly scenario. The 8D sample uses a fixed "status as of" date so the example looks the same every time; set it to today's date to track a live 8D.
- Edits are held in the browser session only. Use the CSV downloads to keep results.

## 4. Screenshots to take (save in docs/screenshots/)

| Filename | What to capture |
|---|---|
| `8d-stepper.png` | 8D page: metrics row and the D0 to D8 stepper (D6 shows the orange overdue ring) |
| `8d-timeline.png` | 8D page: planned-versus-actual timeline with "1 d late", "1 d early" and "overdue 8 d" labels |
| `kaizen-matrix.png` | Kaizen page, Impact / effort matrix tab, with the quick-wins warning above it |
| `kaizen-funnel.png` | Kaizen page, Status funnel tab |
| `kaizen-cumulative.png` | Kaizen page, Cumulative savings tab |
| `kaizen-pdca.png` | Kaizen page, PDCA cycle tab |
