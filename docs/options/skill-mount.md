####> This option file is used in:
####>   ramalama sandbox goose, ramalama sandbox opencode, ramalama sandbox pi
####> If this file is edited, make sure the changes
####> are applicable to all of those.
#### **--skill-mount**=*path*
Base path inside the container to extract or mount skills, agents, and
plugins. Each kind gets its own subdirectory under this path, e.g.
*path*/skills/*name*. Defaults to `/root/.agents`.