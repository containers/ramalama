####> This option file is used in:
####>   ramalama run, ramalama sandbox goose, ramalama sandbox opencode, ramalama serve
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--model-draft**

A draft model is a smaller, faster model that helps accelerate the decoding
process of larger, more complex models, like Large Language Models (LLMs). It
works by generating candidate sequences of tokens that the larger model then
verifies and refines. This approach, often referred to as speculative decoding,
can significantly improve the speed of inferencing by reducing the number of
times the larger model needs to be invoked.

Use --runtime-args to pass the other draft model related parameters.
Make sure the sampling parameters like top_k on the web UI are set correctly.
