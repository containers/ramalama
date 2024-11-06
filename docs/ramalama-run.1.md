% ramalama-run 1

## NAME
ramalama\-run - run specified AI Model as a chatbot

## SYNOPSIS
**ramalama run** [*options*] *model* [arg ...]

## OPTIONS

#### **--authfile**=*password*
path of the authentication file for OCI registries

#### **--help**, **-h**
show this help message and exit

#### **--name**, **-n**
name of the container to run the Model in

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

## DESCRIPTION
Run specified AI Model as a chat bot. RamaLama pulls specified AI Model from
registry if it does not exist in local storage. By default a prompt for a chat
bot will be started. When arguments are specified, the arguments will be given
to the AI Model and the output returned without entering the chatbot.

## EXAMPLES

Run command without arguments starts a chatbot
```
ramalama run granite

>
```

```
ramalama run merlinite "when is the summer solstice"
The summer solstice, which is the longest day of the year, will happen on June ...
```

Run command with a custom prompt and a file passed by the stdin
```
cat file.py | ramalama run granite-code 'what does this program do?'

This program is a Python script that allows the user to interact with a terminal. ...
 [end of text]
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
