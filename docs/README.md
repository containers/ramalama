## Directory Structure

|                                      | Directory                   |
| ------------------------------------ | --------------------------- |
| Markdown source for man pages        | docs/*md                    |
| target for output                    | docs/*.[15]                 |
| man pages                            | docs/*.[15]                 |

## Build the Docs

To build standard man pages, run `make install-tools` followed by `make docs`. Results will be in `docs`.
