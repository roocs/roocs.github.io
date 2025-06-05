# ROOCS Website

[ROOCS Website](https://roocs.github.io/) is the front page for the roocs project.

## Contributing

Contributions are welcome. Feel free to open a pull request with changes.

## Running it Locally

It can be helpful to preview changes on your computer before opening a pull request. *ROOCS website* uses the [MkDocs static site generator](https://www.mkdocs.org/). After forking or cloning the repository, perform the following steps to generate the site and preview it:

```
# build conda env with mkdcos
conda env create
conda activate roocs

# build docs
mkdocs build

# view docs locally
mkdocs serve
```

Open browser: http://127.0.0.1:8000


## Deployment

Pull requests merged to the main branch are automatically deployed to the production website.

## License

The content of this project itself is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International license](https://creativecommons.org/licenses/by-sa/4.0/), and the underlying source code used to format and display that content is licensed under the [MIT license](LICENSE.txt).
