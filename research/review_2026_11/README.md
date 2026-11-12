# Strategy review, 12 November 2026

Four independent reviews of the Standard Bank / Nedbank strategies, run once on development data only (every series truncated at 31 March 2026): overfitting, execution and costs, design, and the copula signal. `summary.md` is the combined summary; the findings and figures are recorded in `research/RESULTS.md` ("Review, 12 November 2026"), and the hypotheses that came out of it are H18 and H19 in `research/PROTOCOL.md`.

The scripts are kept as they were run, for the record. They read the repository's data (`REPO` is the repository root) and wrote their intermediate files and outputs to `/tmp/jse-review/<dimension>/`; large intermediates (pickles, arrays, placebo draws) are not kept. Run from the repository root with `service/.venv/bin/python`, each in its own folder's context (`common.py` / `core.py` / `base.py` first). They are not part of the pipeline and nothing reads their outputs.
