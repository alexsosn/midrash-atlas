# Link Exegesis

An offline-first Sefaria citation atlas and research instrument built from
Sefaria's public Links API.
The generated `report.html` contains the complete derived dataset and can be
opened directly; every Tanakh verse and graph evidence reference links back to
its text on Sefaria.

## Build

Create a Python environment and install the runtime dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Refresh the chapter cache, then generate the atlas:

```bash
python pull.py
python export_atlas.py
python layout_work_graphs.py
python layout_collection_graphs.py
```

The two layout commands use Graphviz `sfdp` to precompute deterministic
coordinates and rewrite the data/report with those layouts embedded. One stable
work layout covers both the locus and raw-pair models; locus edges determine its
geometry and low-weight raw-only links place verses that occur solely in the raw
model. Smaller work graphs retain the in-browser force layout.

The collection-layout command performs the same precomputation for both edge
models of every complete collection graph and stores Louvain membership with
the coordinates. The browser reconstructs all collection edges from exact
source evidence; the support slider never changes which vertices or edges are
part of the analytical graph.

This reads one cached Links API response for each of the 929 Tanakh chapters
and writes:

- `atlas_data.json`: reusable profiles, collection/work hierarchies, compact
  exact source evidence, complete collection/work layouts, and provenance;
- `report.html`: standalone pair-comparison lab, collection and work
  dendrograms, citation profiles, and community-aware graph explorer.

To use a cache elsewhere:

```bash
SEFARIA_CACHE=/path/to/cache python export_atlas.py
```

Run extraction checks with:

```bash
python -m unittest test_dataset.py test_graph_model.py test_atlas.py test_research_export.py
```

## Research exports

Turn any collection or individual work into an auditable evidence bundle:

```bash
python research_export.py --category Kabbalah --list-works

python research_export.py \
  --category Kabbalah \
  --work "Maaseh Rokeach on Mishnah" \
  --mode loci \
  --min-support 1
```

Each bundle contains:

- `nodes.csv`, with canonical verse refs, Sefaria links, communities, degree,
  and weighted degree;
- `edge-evidence.csv`, in long form with one row per co-citation edge and exact
  supporting source ref, plus Sefaria links, support, weight, surprise, and
  textual-distance band;
- `manifest.json`, recording the atlas SHA-256, method version, data timestamp,
  selection, filters, graph scope, row counts, and output checksums.

Exports reconstruct the full selected graph from compact source evidence. They
are not restricted to the top-node slice used for readable browser display.

See [RESEARCH_ROADMAP.md](RESEARCH_ROADMAP.md) for the prioritized validity,
provenance, and philological-review work still needed before publishable claims.

## Methodological decisions

- Canonical refs are validated against the full Tanakh response from Sefaria's
  Shape API in `tanakh_shape.json` (recorded 2026-07-17: 39 Sefaria book
  indexes, 929 chapters, 23,206 verses).
- A range link has total citation weight 1, divided over its canonical verses.
- If duplicate Sefaria records assign different ranges to the same exact
  source–verse pair, the shortest (most specific) anchor determines its weight;
  input file and record order cannot change the result.
- Expanded anchors are clipped to the chapter represented by each cache file;
  this prevents long ranges from being counted once per cached chapter.
- The exact Sefaria source ref is the co-citation discourse unit. This avoids
  collapsing structurally different texts at inconsistent depths. Single
  anchors spanning more than 10 verses are excluded from co-citation because
  they do not establish all pairwise links.
- The default graph merges, within each source, targets separated by at most
  one uncited verse into a citation locus. It creates no edge within a locus.
  A source with two or more distinct loci contributes total edge weight one,
  distributed across locus pairs and their constituent verse pairs.
- Raw mode retains every verse pair with integer source support for auditing.
  Unexpected-association mode uses the locus graph and reports shrunken
  log2 observed/expected lift. Its expectation controls for both endpoint
  popularity and seven textual-distance bands; it is a diagnostic ranking,
  not a probability or proof of influence.
- Work-level dendrograms include up to 18 works per category with at least 30
  normalized citation weight and 15 distinct cited Tanakh verses. Coverage and
  the filter threshold are displayed in the instrument.
- Collection and work graphs retain support-1 edges. The source-support control
  always starts at 1; single-source edges are drawn quietly so they remain
  auditable without visually competing with repeated evidence.
- Collection graphs use Louvain communities; an individual work uses connected
  components because sparse work-level evidence does not support a stable
  modularity partition. Layouts use seed 17, and every displayed edge retains
  its complete list of exact Sefaria source refs.
- Individual-work graphs contain every vertex and edge in the chosen model.
  The former top-120 centrality selection has been removed; labels and edge
  emphasis change with zoom and filters, but the analytical graph does not.
- Collection graphs likewise contain every vertex and edge. The retained
  `collection_previews` dataset is a compact build-time diagnostic only and is
  never used by the interactive research graph.

Source APIs: [Links](https://developers.sefaria.org/reference/get-links),
[Shape](https://developers.sefaria.org/reference/get-shape), and
[Sefaria text references](https://developers.sefaria.org/docs/text-references).
