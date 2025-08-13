#!/bin/bash

YAMLDIR="$(dirname $0)"
TMPSCRIPT="$(mktemp)"
trap "rm $TMPSCRIPT" 0
awk '/script:/ {in_script = 1; next}; {if (in_script) print substr($0, 7)}' "$YAMLDIR/create-override-snapshot.yaml" > "$TMPSCRIPT"
python3 "$TMPSCRIPT"
