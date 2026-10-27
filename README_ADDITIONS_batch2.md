<!-- Paste into README.md. Do not commit this file. -->

## 1. Module table: add these rows (CI Toolkit section)

| Section | Module | What it does |
|---|---|---|
| CI Toolkit | 5 Why Analysis | Problem statement plus an editable chain of causes (up to 10 levels) with evidence and a Verified tick. Draws the causal chain from the problem to the root-cause box, flags unverified levels, and gives a backwards "therefore" reading as a logic check. CSV download. |
| CI Toolkit | Fishbone (Ishikawa) | Editable cause table (6M categories, optional sub-causes, Suspected tick) drawn as a fishbone diagram. Suspected causes are shown in red and listed below the chart. Per-category counts and CSV download. |

Sidebar URL paths: `/five-why` and `/fishbone`.

## 2. Engineering notes: add

**5 Why**
- Row order defines the level: row 1 is Why 1, the last row is treated as the root cause. The tool does not decide whether a cause is a true root cause; it lists checks (fewer than three levels, unverified levels, unverified root cause).
- Verified means the cause was checked against data, observation or records. The sample data leaves the last level unverified to show how that is flagged.
- The "read backwards" list turns each pair of rows into "cause, therefore, effect" so a gap in the logic is easy to see.

**Fishbone**
- Categories are the 6M: Man (People), Method, Machine, Material, Measurement, Mother Nature (Environment, shown as "Environment"). Common alternative names are accepted in pasted data (for example Equipment for Machine, Inspection for Measurement).
- The diagram lists possible causes only. It does not rank them or show which one is true; the Suspected tick marks what the team plans to verify.
- Rows with the same category and cause are merged into one cause with several sub-causes.

## 3. Limitations: add

- 5 Why supports one causal chain. Problems with several independent causes need one chain per cause (or a fishbone first).
- Fishbone labels are shortened to about 34 characters (30 for sub-causes) in the diagram; hover shows the full text. Label widths are fixed in chart units, so on a narrow window (phone) labels can overlap. Use a wide window for screenshots.
- Both tools use simulated sample data for a generic machining/sealing scenario, not a real event.
- Edits are held in the browser session only; use the CSV downloads to keep results.

## 4. Screenshots to take (save in docs/screenshots/)

| Filename | What to capture |
|---|---|
| `5why-chain.png` | 5 Why page: the chain diagram down to the green root-cause box (the dashed or warning item is fine to leave in) |
| `fishbone-diagram.png` | Fishbone page: full diagram with the two red suspected causes and the info line below |
