# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub:
**Security → Report a vulnerability** on this repository. Do not open a public
issue. You will get a reply within 7 days.

## Secrets

Asteria never needs a secret in the repository. Keys and logins (Cesium ion
token, Space-Track login) live only in `.env.local` / `.env` at the repo root,
which are git-ignored; `.env.example` documents every setting with blank values.

- Never commit a filled-in settings file. If you do, rotate the key at once:
  removing it in a later commit does not remove it from git history.
- Restrict a Cesium ion token to the `assets:read` scope and to the URLs that
  serve your console.
- `NEXT_PUBLIC_` values are compiled into the browser bundle by design, so they
  are public to anyone who loads the console. Only a URL-restricted, read-only
  token belongs there.
- Space-Track passwords are only sent to Space-Track's login endpoint and are
  never logged.

## Scope

The engine API is read-only and serves hash-verified artifacts; it accepts no
uploads. Run it behind a reverse proxy with TLS if you expose it beyond your
own machine, and set `ASTERIA_WEB_ORIGINS` to your console's origin.
