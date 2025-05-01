# Ramalama Docs
Ramalama uses man pages

## Directory Structure
| Description                          | Directory                   |
| ------------------------------------ | --------------------------- |
| Markdown source for man pages        | docs/*md                    |
| target for output                    | docs/*.[15]                 |
| man pages                            | docs/*.[15]                 |

## Build the Docs
To build standard man pages,

- Make sure in `ramalama` directory

```
cd ramalama
```

- Install tools

```
make install-tools
```

- Make the man docs

```
make docs
```

- Results will be in `docs`

```
cd docs
```
