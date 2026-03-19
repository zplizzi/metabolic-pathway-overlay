# Metabolic Pathway Overlay

Interactive viewer for metabolic pathway diagrams with lab result overlays. Renders `.drawio` pathway files as SVG, then overlays your test data — clickable metabolite nodes show test history, sparklines, and reference ranges across multiple lab sources.

## Setup

Install [uv](https://github.com/astral-sh/uv).

Put your test data in `data/test_data`, or run with `--test_data_dir data/sample_test_data` to use the sample data.

## Running

```
uv run python src/metabolic_pathway_overlay/server.py --port 5555
```

View at http://localhost:5555.

### CLI options

```
--port PORT            Port to serve on (default: 5555)
--pathways_dir DIR     Path to .drawio diagram files (default: data/pathways)
--test_data_dir DIR    Path to test data CSVs (default: data/test_data)
```

## Project structure

```
data/
  pathways/                     .drawio diagram files (one per pathway)
  sample_test_data/             Example CSVs (committed, safe for public release)
  test_data/                    Your real test data (gitignored)
src/metabolic_pathway_overlay/  Project code
```

## Third-party content

The `full_figure_1.drawio` pathway diagram is derived from [Figure 1](https://bornfree.life/learn/#figure1) by Joshua Leisk and is subject to its own copyright. It is not covered by this project's license.

## Test data format

Place CSVs in the test data directory. The following formats are supported:

- **labcorp.csv** — `date,test_name,description,normal_low,normal_high,value`
- **theriome_aristotle.csv** — Single-timepoint metabolomics with `Analyte,Value,Low,High,Deviation%,Status`
- **mosaic_organic_acids.csv** — Wide format with `val_YYYY_MM_DD` / `status_YYYY_MM_DD` date columns
- **vibrant_micronutrients.csv** — Wide format with `YYYY-MM-DD` date columns, keyed by `Analyte,Sample_Type`
- **css_cellular_micronutrient_assay.csv** — Wide format with `YYYY-MM-DD` date columns, keyed by `analyte`

Sample data is provided in `data/sample_test_data/`.

## How it works

- **Viewer mode** — Parses `.drawio` XML and renders SVG. Metabolite overlays (badges, click panels) are attached by matching node labels to analyte mappings in `analyte_mapping.py`.
- **Edit mode** — Embeds the draw.io editor via iframe + postMessage API. Saves back to the server via PUT. Exiting re-renders from updated XML.
- **Share** — `GET /api/share` returns a self-contained HTML file with all pathway and analyte data embedded, no server needed.

## API

```
GET  /api/pathways          List available pathway names
GET  /api/pathways/<name>   Get .drawio XML for a pathway
PUT  /api/pathways/<name>   Save .drawio XML
GET  /api/analyte-data      Analyte data mapped to pathway node labels
GET  /api/all-analytes      All analytes from all sources, grouped by source
GET  /api/share             Download self-contained HTML viewer
```

## Comparison tool

Screenshots the custom HTML renderer and the diagrams.net viewer side-by-side for visual comparison (useful in agent loops).

```
uv run python src/scripts/compare.py [pathway_name]
```
