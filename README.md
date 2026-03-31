# ROOCS Website

[ROOCS Website](https://roocs.github.io/) is the front page for the roocs project.

## Contributing

Contributions are welcome. Feel free to open a pull request with changes.

## Running it Locally

Preview changes locally before opening a pull request. This site uses [MkDocs](https://www.mkdocs.org/).

```
# create conda environment
conda env create
conda activate roocs

# build docs
mkdocs build

# serve docs locally
mkdocs serve
```

Open browser: http://127.0.0.1:8000

## Extract Monthly Download Stats

Use `scripts/extract_stats.py` to aggregate monthly request/download metrics from dashboard HTML files.

Use the same conda environment setup shown above (`conda env create`, `conda activate roocs`), then run:

```bash
python scripts/extract_stats.py --start 2025-04 --end 2026-02 --site dkrz --quiet
```

This writes:

`docs/downloads/dashboard/<site>-monthly-<start>_to_<end>_metrics.csv`


## Deployment

Pull requests merged to the main branch are automatically deployed to the production website.

## License

The content of this project itself is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International license](https://creativecommons.org/licenses/by-sa/4.0/), and the underlying source code used to format and display that content is licensed under the [MIT license](LICENSE.txt).
