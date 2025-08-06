% ramalama-daemon 1

## NAME
ramalama\-daemon - run a RamaLama REST server

## SYNOPSIS
**ramalama daemon** [*options*] [start|run]

## DESCRIPTION
Inspect the specified AI Model about additional information
like the repository, its metadata and tensor information.

## OPTIONS

#### **--help**, **-h**
Print usage message

## COMMANDS

#### **start**
pepares to run a new RamaLama REST server so it will be run either inside a RamaLama container or on the host

#### **run**
start a new RamaLama REST server

## EXAMPLES

Inspect the smollm:135m model for basic information
```
$ ramalama inspect smollm:135m
smollm:135m
   Path: /var/lib/ramalama/models/ollama/smollm:135m
   Registry: ollama
   Format: GGUF
   Version: 3
   Endianness: little
   Metadata: 39 entries
   Tensors: 272 entries
```

Inspect the smollm:135m model for all information in json format
```
$ ramalama inspect smollm:135m --all --json
{
    "Name": "smollm:135m",
    "Path": "/home/mengel/.local/share/ramalama/models/ollama/smollm:135m",
    "Registry": "ollama",
    "Format": "GGUF",
    "Version": 3,
    "LittleEndian": true,
    "Metadata": {
        "general.architecture": "llama",
        "general.base_model.0.name": "SmolLM 135M",
        "general.base_model.0.organization": "HuggingFaceTB",
        "general.base_model.0.repo_url": "https://huggingface.co/HuggingFaceTB/SmolLM-135M",
        ...
    },
    "Tensors": [
        {
            "dimensions": [
                576,
                49152
            ],
            "n_dimensions": 2,
            "name": "token_embd.weight",
            "offset": 0,
            "type": 8
        },
        ...
    ]
}
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Feb 2025, Originally compiled by Michael Engel <mengel@redhat.com>
