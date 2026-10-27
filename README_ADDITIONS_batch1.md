<!-- Paste into README.md. Do not commit this file. -->

## 1. Module table: add these rows (adjust columns to match your existing table)

| Section | Module | What it does |
|---|---|---|
| CI Toolkit | FMEA (DFMEA / PFMEA) | Failure mode and effects analysis with a Design / Process toggle. Classic RPN (Severity x Occurrence x Detection, 1-10). RPN Pareto, severity x occurrence heat map, before/after RPN bars. Severity >= 9 flagged regardless of RPN. CSV download. |
| CI Toolkit | 5S Audit | Scored checklist (0-4 per item) for Sort, Set in order, Shine, Standardize, Sustain. Radar chart against a target, score trend across audits, weakest-S callout with its lowest-scoring items. |

Also update the sidebar description: the sidebar now has two sections, **Operations Analytics** (SPC, OEE, Pareto, Maintenance & MTBF, Line Balancing & Takt) and **CI Toolkit** (DMAIC board, FMEA, 5S audit). Each tool has its own URL path, for example `/fmea` and `/five-s`.

## 2. Engineering notes: add

**FMEA**
- RPN = S x O x D, each rated 1 to 10 (whole numbers). Rows with a missing or invalid rating are excluded and listed under the table.
- Any failure mode with Severity >= 9 is flagged regardless of its RPN. The sample data includes one such row with an RPN below the default threshold.
- The RPN review threshold is set by the user (default 100). It is a team choice, not a standard value.
- Pareto ranks by RPN; ties are ordered by higher Severity first. Cumulative % is relative to the total RPN of all rows, including rows not shown when "failure modes shown" is limited.
- Heat map shading is S x O only. Detection is not on that chart.
- Before/after compares the current RPN with the RPN from the revised S/O/D ratings. Only rows with all three revised ratings are compared.

**5S audit**
- Item scores run 0 to 4. S score % = points / (4 x items scored). Items with a blank score are not counted.
- Overall score = average of the five S percentages, so each S counts equally regardless of how many items it has.
- The trend chart uses the earlier-audits table, plus the current checklist result if the checkbox is on. If the current audit date matches an earlier audit date, the current result replaces it.

## 3. Limitations: add

- FMEA uses the classic RPN method. It does not implement the AIAG-VDA Action Priority tables. RPN has known weaknesses: different S/O/D combinations can give the same RPN, and the product treats ordinal ratings as numbers.
- The rating scale text in the FMEA page is generic orientation, not a reproduction of any standard. Use your organisation's scales.
- FMEA and 5S sample data are simulated, for a generic mechanical sub-assembly and a generic workcell. They are not from a real product, employer or audit.
- Edits are held in the browser session only. Reloading the page or switching tool resets tables to the sample data; use the CSV download to keep FMEA results.
- 5S checklist items and the 0-4 scale descriptions are generic; they are not a certified audit standard.

## 4. Screenshots to take (save in docs/screenshots/)

| Filename | What to capture |
|---|---|
| `sidebar-two-sections.png` | Sidebar with "Operations Analytics" and "CI Toolkit" headings visible |
| `fmea-rpn-pareto.png` | FMEA page, RPN Pareto tab, red (Severity >= 9) bars visible |
| `fmea-so-heatmap.png` | FMEA page, S x O heat map tab |
| `fmea-before-after.png` | FMEA page, Before / after tab |
| `5s-radar-weakest.png` | 5S page: radar chart plus the weakest-S callout |
| `5s-trend.png` | 5S page: score trend chart |
