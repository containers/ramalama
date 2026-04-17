####> This option file is used in:
####>   ramalama run
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--summarize-after**=*N*
Automatically summarize conversation history after N messages to prevent context growth.
When enabled, ramalama will periodically condense older messages into a summary,
keeping only recent messages and the summary. This prevents the context from growing
indefinitely during long chat sessions. Set to 0 to disable (default: 4).
