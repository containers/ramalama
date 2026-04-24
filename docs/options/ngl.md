####> This option file is used in:
####>   ramalama bench, ramalama perplexity, ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--ngl**
Number of GPU layers: `0` means CPU inferencing, `999` means use max GPU layers.
Default is `-1`; for llama.cpp backends, negative values are mapped to `999` (max layers).
