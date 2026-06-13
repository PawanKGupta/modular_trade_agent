# Security Policy

## Supported Versions

| Version / branch | Supported |
|------------------|-----------|
| `main` (latest) | Yes |
| Older release tags | Best effort only |

## Reporting a Vulnerability

Email the maintainers privately (do not open a public issue for undisclosed vulnerabilities).

Include:

- Description and impact
- Steps to reproduce
- Affected component (API, web, broker integration)
- Suggested fix if known

We aim to acknowledge reports within a few business days.

## Scope

In scope: authentication, user data isolation, broker credential handling, trading execution paths, deployment secrets.

Out of scope: third-party broker APIs, user-managed infrastructure misconfiguration.

## Safe harbor

Good-faith security research on your own deployment is welcome. Do not access other users' data or production systems without permission.

## Documentation

- [docs/security/USER_DATA_SECURITY.md](docs/security/USER_DATA_SECURITY.md)
- [docs/security/TOKEN_SECURITY.md](docs/security/TOKEN_SECURITY.md)
