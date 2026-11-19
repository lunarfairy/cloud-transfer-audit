# Cross-Provider Cloud Transfer Audit

Code, OpenTofu configurations, provider schemas, coded datasets, automated grader, and trial power simulation for auditing cross-provider correspondence across AWS, Azure, Google Cloud, and OpenStack.

## Requirements

- Python 3.11: `pip install -r requirements.txt`
- OpenTofu 1.13.2 (optional; needed only for `code/conformance_check.py`)

## Usage

```bash
python code/reproduce.py                 # Recompute metrics and write tex/results_macros.tex
python code/make_tables.py               # Write manuscript tables to tex/tab_*.tex
python code/make_supplement_tables.py    # Write supplementary tables to tex/supp_*.tex
python code/make_figures.py              # Write Figures 1-6 to fig/
python code/grader.py ra/gcp gcp         # Grade GCP or Azure Terraform configs
python code/trial_simulation.py 2000     # Run trial power simulations
```

## Structure

- `code/` -- audit, agreement, retrieval, table/figure, grader, and simulation scripts
- `ra/` -- OpenTofu reference implementations and mock conformance tests (`aws`, `azure`, `gcp`, `openstack`)
- `schemas/` -- exported provider schemas (`schemas.json.gz`)
- `data/` -- slot catalogue, coded decisions, semantic adjudication, retrieval, and simulation CSV/JSON files
- `workbook/` -- blinded human-coding workbook and keys

## License

MIT License; see [LICENSE](LICENSE).
