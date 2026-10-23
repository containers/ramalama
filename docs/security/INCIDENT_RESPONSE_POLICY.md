## Incident Response Policy

### Scope
This policy covers security incidents affecting this project, including its source code, infrastructure, release pipeline, maintainer accounts, and contributor trust.

Security takes place in two places - before and after something goes wrong.  

Other processes and policy should be in place to be preventative and cover things like reviewing merge requests before they are accepted, and vetting new contributions and contributors to a project before they are trusted. This "Incident Response Policy", or IRP, is reactive and covers what happens if something has already gone wrong.

### What constitutes an incident

An incident can be many things.  In this context we are talking about hostile events that threaten the security of the product.
- Unauthorized code changes (e.g. a malicious commit or compromised maintainer account)
- Leaked secrets, credentials, or signing keys
- A vulnerability being actively exploited in the wild
- Compromised build infrastructure
- A compromised endpoint belonging to someone with repository or release access

### Reporting a security issue
- Report to our GitHub [security advisory page](https://github.com/containers/ramalama/security/advisories/new) and follow the rules/template listed.
- Never open a public issue for an active exploit or a leaked secret.
- We aim to acknowledge all reports within 48 hours.

### Response process

1. **Acknowledgment**: We will acknowledge receipt of your vulnerability report within 48 hours
2. **Triage** — Confirm the incident, assess its scope and severity.
3. **Contain** — Revoke credentials, roll back affected commits, rotate keys as needed.
3. **Eradicate** — Fix the root cause and patch the vulnerability.
4. **Recover** — Restore normal operations; re-issue a release if required.
5. **Disclose** — Notify affected users and publish an advisory, following coordinated disclosure practices.
6. **Review** — Conduct a post-incident review and document follow-up actions to prevent recurrence. We will credit you for the discovery when we publish the fix (unless you prefer to remain anonymous).