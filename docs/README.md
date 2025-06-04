# RamaLama Docs
RamaLama uses man pages

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

## Run the Tests
To run the tests,

- Install [pytest](https://docs.pytest.org/en/stable/getting-started.html) 

- Run tests with

```
pytest
```

or

```
pytest path/to/test_file.py
```

(which runs an individual test file)
