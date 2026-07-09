% ramalama-list 1

## NAME
ramalama\-list - list all downloaded AI Models

## SYNOPSIS
**ramalama list** [*options*]

**ramalama ls** [*options*]

## DESCRIPTION
List all the AI Models in local storage.

To list models currently loaded by a running inference server (for example after
**ramalama serve**), use **ramalama-models(1)** instead.

When a downloaded model URI matches an entry in **shortnames.conf**, the table includes a **SHORTNAME** column with the corresponding alias (for example **gemma3:12b** for **hf://ggml-org/gemma-3-12b-it-GGUF**). Models with no configured alias leave **SHORTNAME** empty. See **ramalama-info(1)** for the configured shortname mappings.

## OPTIONS

#### **--all**
include partially downloaded Models

#### **--help**, **-h**
show this help message and exit

#### **--json**
print Model list in json format

#### **--noheading**, **-n**
do not print heading

#### **--order**
order used to sort the AI Models. Valid options are 'asc' and 'desc'

#### **--sort**
field used to sort the AI Models. Valid options are 'name', 'size', and 'modified'.

## EXAMPLES

List all Models downloaded to the local store
```console
$ ramalama list
SHORTNAME   NAME                                                                MODIFIED     SIZE
smollm:135m ollama://smollm:135m                                                16 hours ago 5.5M
            huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf 14 hours ago 460M
            ollama://granite-code:3b (partial)                                  5 days ago   1.9G
            ollama://granite-code:latest                                        1 day ago    1.9G
            ollama://moondream:latest                                           6 days ago   791M
```

List all Models in JSON format (each object includes **shortname**, **name**, **modified**, and **size**)
```json
$ ramalama list --json
[
  {
    "shortname": "gemma3:12b",
    "name": "hf://ggml-org/gemma-3-12b-it-GGUF",
    "modified": "2026-05-21T12:00:00+00:00",
    "size": 8150000000
  },
  {
    "shortname": "",
    "name": "ollama://moondream:latest",
    "modified": "2026-05-15T08:00:00+00:00",
    "size": 829000000
  }
]
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-models(1)](ramalama-models.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
