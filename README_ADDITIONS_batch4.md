<!-- Paste into README.md. Do not commit this file. -->

## 1. Module table: add these rows

| Section | Module | What it does |
|---|---|---|
| Operations Analytics | Gage R&R | Crossed Gage R&R study with the ANOVA method. Simulate a gauge (sliders for part, repeatability, operator and interaction variation) or edit/upload measurements. Reports repeatability, reproducibility, part-to-part, % study variation, % contribution, % tolerance and distinct categories, with a verdict against the common AIAG guideline limits. Charts: variation components, readings by part, by operator, operator-by-part interaction. |
| CI Toolkit | Which Tool When? | Guide to all tools by stage (detect, analyze, fix, prevent), a situation picker that suggests an order of tools with the reason for each step, and a one-line summary of what each tool needs and produces. |

Sidebar URL paths: `/gage-rr` and `/guide`. The sidebar now has 6 tools under Operations Analytics and 8 under CI Toolkit.

## 2. Engineering notes: add

**Gage R&R**
- Design: crossed (every operator measures every part), balanced (same number of readings in every part-operator cell, at least 2). Unbalanced data is rejected with the cells that differ listed.
- Method: two-way ANOVA with replication. Variance components: repeatability = error mean square; operator and part from mean-square differences; interaction from (interaction MS - error MS) / readings per cell. Negative estimates are set to 0 and noted.
- The operator-by-part interaction is tested with an F-test. If its p-value is above the alpha setting (default 0.25) it is removed from the model and pooled with repeatability. Alpha is adjustable.
- Total Gage R&R = repeatability + reproducibility (operator + interaction). % Contribution uses variances and sums to 100%. % Study variation uses standard deviations and does not. Study variation spread = 6 standard deviations. % Tolerance = 6 x gauge standard deviation / (USL - LSL).
- Distinct categories = floor(1.41 x part sd / gauge sd).
- Guideline limits used for the verdict: below 10% acceptable, 10% to 30% marginal, above 30% not acceptable, at least 5 distinct categories. These are common guideline values from the AIAG MSA manual; customers and organizations can set different ones.
- The F-distribution p-value is computed in the module (regularized incomplete beta function), so the app needs no extra package. It is tested against scipy, and the sums of squares against an independent calculation. Variance components are recovered from large simulated studies with known inputs.

**Which Tool When?**
- Each tool is tagged with one or more stages. A test checks that every page in the sidebar appears in the guide and every guide link points to a real page.

## 3. Limitations: add

- Gage R&R covers the crossed ANOVA study only. It does not do nested designs (destructive tests), attribute (pass/fail) agreement studies, bias, linearity or stability studies.
- The default data is simulated. It shows how the method behaves; it does not describe any real gauge. The percentages depend on the random seed and on the number of parts and operators; small studies give wide uncertainty on every estimate.
- The tool has not been compared with a published worked example. If you have one (for example from the AIAG MSA manual or statistical software), upload it in the "Edit or upload data" mode and compare.
- The guide's suggested orders are generic starting points, not a required procedure.
- Guide links open in a new tab, so edits in the current tab are not carried over.

## 4. Screenshots to take (save in docs/screenshots/)

| Filename | What to capture |
|---|---|
| `grr-verdict-components.png` | Gage R&R page: verdict banner, four metrics and the Variation components tab |
| `grr-by-part.png` | Gage R&R page, By part tab |
| `grr-interaction.png` | Gage R&R page, Interaction tab |
| `guide-stages.png` | Which Tool When? page: the four-stage diagram |
