# Security

This is a local research CLI, not a hosted service. Never supply secrets in configs, dataset files or issues. Run only trusted project code in an isolated environment. Raw downloads are restricted to explicitly supported NESO hosts and a size limit; still treat source files as untrusted data.

Report a suspected vulnerability privately using this repository's GitHub **Security → Report a vulnerability** feature when available, or the maintainer contact linked from [the portfolio](https://abhijith-sivaprasadan.github.io/#contact). Do not publish exploit details or sensitive files in a public issue. There is no guaranteed response time or security-support SLA for this exploratory release.

Manifests detect accidental edits relative to recorded hashes. They are not signatures and do not establish authenticity against an attacker who can replace both data and manifest. Scientific correctness concerns without sensitive details may be reported as normal issues.
