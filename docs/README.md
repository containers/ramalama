# RamaLama Documentation

The online man pages and other documents regarding RamaLama can be found at
[Read The Docs](https://ramalama.readthedocs.io).  The man pages
can be found under the [Commands](https://ramalama.readthedocs.io/en/latest/Commands.html)
link on that page.

# Build the Docs

## Directory Structure

|                                      | Directory                   |
| ------------------------------------ | --------------------------- |
| Markdown source for man pages        | docs/*md                    |
| target for output                    | docs/*.[15]                 |
| man pages                            | docs/*.[15]                 |

## Manpage Syntax

The syntax for the formatting of all man pages can be found [here](MANPAGE_SYNTAX.md).

## Local Testing

To build standard man pages, run `make docs`. Results will be in `docs`.

To build HTMLized man pages: Assuming that you have the
[dependencies](https://ramalama.io/getting-started/installation#build-and-run-dependencies)
installed, then also install (showing Fedora in the example):

```
$ sudo dnf install python3-sphinx python3-recommonmark
$ pip install sphinx-markdown-tables myst_parser
```
(The above dependencies are current as of 2022-09-15. If you experience problems,
please see [requirements.txt](requirements.txt) in this directory, it will almost
certainly be more up-to-date than this README.)

After that completes, cd to the `docs` directory in your RamaLama sandbox and then do `make html`.

You can then preview the html files in `docs/build/html` with:
```
python -m http.server 8000 --directory build/html
```
...and point your web browser at `http://localhost:8000/`
