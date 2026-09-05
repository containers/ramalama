####> This option file is used in:
####>   ramalama sandbox goose, ramalama sandbox opencode, ramalama sandbox pi
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--internal-network**
Use a private network without internet access for the sandbox container.
Only available when --url is not specified (i.e. when rama starts its own model server).
If --network is given, the named network must not already exist, otherwise the command
fails.
