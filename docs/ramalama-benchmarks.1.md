% ramalama-benchmarks 1

## NAME
ramalama\-benchmarks - view and interact with historical benchmark results

## SYNOPSIS
**ramalama benchmarks** [*options*] *command* [*args*...]

## DESCRIPTION
View and interact with historical benchmark results.
Results are stored as newline-delimited JSON (JSONL) in a `benchmarks.jsonl` file.
The storage folder is shown in `ramalama benchmarks --help` and can be
overridden via `ramalama.benchmarks.storage_folder` in `ramalama.conf`.

## OPTIONS

#### **--help**, **-h**
show this help message and exit

## COMMANDS

#### **list**
list benchmark results

## LIST OPTIONS

#### **--limit**=LIMIT
limit number of results to display

#### **--offset**=OFFSET
offset for pagination (default: 0)

#### **--format**=\{table,json\}
output format (table or json) (default: table)

## EXAMPLES

```
ramalama benchmarks list
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-bench(1)](ramalama-bench.1.md)**, **[ramalama.conf(5)](ramalama.conf.5.md)**

## HISTORY
Jan 2026, Originally compiled by Ian Eaves <ian@ramalama.com>
