# Local environment and secrets

This project uses a local `.env` file for machine-specific configuration.

Copy the example file before running anything locally:

```bash
cp .env.example .env
```

Then fill in the values you need.

## Secrets

Secrets belong in `.env`, not in the repository.

Rules:

- never commit real keys or tokens
- never paste live credentials into chat, logs, or agent prompts
- if a secret is exposed, rotate it instead of assuming `.gitignore` fixes the exposure
- keep `.env` listed in `.gitignore`
- keep `.env.example` free of real values

## Prime Intellect

If you use Prime Intellect integration, set the documented environment variable in `.env` and confirm the exact variable name from Prime Intellect documentation/CLI before relying on it.

Do not invent variable names. Use the one Prime documents.

## Other local values

Add other local-only settings here as the project grows, for example:

- paths
- ports
- seeds
- machine-specific runtime flags

If a setting is not secret but is machine-specific, prefer documenting it locally rather than baking it into the repo.
