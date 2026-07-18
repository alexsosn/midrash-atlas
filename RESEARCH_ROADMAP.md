# Research roadmap

The atlas is useful for discovery, but graph structure is not itself evidence
of historical influence. Development should prioritize the steps that make a
claim reproducible, bias-aware, and inspectable by a philologist.

## P0 — prerequisites for publishable analysis

1. **Freeze and identify every data snapshot.** Record a checksum manifest for
   the 929 cached API responses, the Shape response, retrieval dates, the Git
   commit, and the Sefaria API parameters. Publish immutable releases and mint a
   DOI (for example through Zenodo) for datasets cited in scholarship.
2. **Measure coverage bias.** Report link coverage by category, work, biblical
   book, link type, and source-ref depth. Distinguish absence of a Sefaria link
   from evidence that a text does not cite a verse. Add a coverage table beside
   every comparison.
3. **Quantify structural stability.** Resample exact source refs and works;
   repeat community detection across seeds and methodological settings; report
   node/edge retention and partition agreement. Treat unstable communities as
   exploratory rather than substantive units.

## P1 — stronger inference

4. **Add bibliographic strata.** Attach author, approximate date, region,
   language, genre, edition, and Sefaria index metadata to works. Sefaria
   categories are editorial groupings, not historical traditions; researchers
   need comparisons within defensible temporal and generic strata.
5. **Use explicit null models.** Preserve the current surprise score as an
   effect-size ranking, then compare it with degree- and distance-preserving
   randomizations. Report empirical intervals and false-discovery correction
   when edges are described as statistically exceptional.
6. **Create a human-validation sample.** Draw a stratified sample of links and
   have domain experts label direct quotation, allusion, commentary target,
   structural range link, and likely false positive. Publish the annotation
   guide and inter-annotator agreement.
7. **Run parameter sensitivity panels.** Show how conclusions change with
   locus gap, long-anchor cutoff, support threshold, top-node limit, distance
   bands, and weighting unit. A claim should survive a reasonable neighborhood
   of defensible settings.

## P2 — researcher workflow

8. **Make browser states citable.** Encode collection, work, model, threshold,
   selected community, and selected verse in the URL; provide a copyable method
   note containing the dataset fingerprint.
9. **Expose evidence export in the browser.** The command-line export already
   writes `nodes.csv`, long-form `edge-evidence.csv`, and `manifest.json` from
   the full exact-source evidence. Add the same operation to the graph controls
   once the localization and stability branches have landed.
10. **Support an evidence-review notebook.** Let researchers save named sets of
    verses/edges, add notes and classifications, and export those annotations
    without modifying the source dataset.
11. **Add regression fixtures from hand-checked cases.** Keep a small, versioned
    set of difficult ranges, adjacent loci, cross-chapter anchors, and known
    Sefaria source refs so methodological changes can be reviewed semantically,
    not only through aggregate counts.

## Claim discipline

- Say **Sefaria link**, **citation profile**, or **co-citation association**
  unless primary-text inspection supports a stronger term.
- Do not infer chronology, dependence, influence, or authorial intent from an
  edge alone.
- Always report the unit of analysis, graph mode, filters, data fingerprint,
  and exact supporting source refs with a published result.
