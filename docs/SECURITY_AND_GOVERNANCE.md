# Repository Security & Branch Protection Policy

This document defines the branch protection and release security policies for the `shashikant649sharma/agent-praxis` repository.

---

## 1. Main Branch Protection Rules

The `main` branch is the canonical production and publication branch. Direct unverified pushes and history modification must be prohibited.

### Required Rules in GitHub Settings
Navigate to **Settings** → **Branches** → **Add branch ruleset / protection rule** for `main`:

1. **Require status checks to pass before merging**:
   - Status check required: `test (3.11)` and `test (3.12)` (from `.github/workflows/ci.yml`).
   - Require branches to be up to date before merging (`strict: true`).
2. **Require a pull request before merging**:
   - Require at least 1 approving review.
   - Dismiss stale pull request approvals when new commits are pushed.
3. **Prevent force pushes**:
   - Do not allow `git push --force` or force-with-lease on `main`.
4. **Prevent deletions**:
   - Prevent deletion of the `main` branch.
5. **Require signed commits** (Recommended for research artifacts):
   - Enforce cryptographic commit signing (`git commit -S`) using GPG or SSH signing keys.

---

## 2. GitHub CLI / API Configuration

Maintainers with repository admin access can apply branch protection via the GitHub CLI:

```bash
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/shashikant649sharma/agent-praxis/branches/main/protection \
  -f required_status_checks='{"strict":true,"contexts":["test (3.11)","test (3.12)"]}' \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1}' \
  -f restrictions=null \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```

---

## 3. PyPI Trusted Publishing (OIDC) Setup

To allow `.github/workflows/cd.yml` to publish release distributions without permanent API tokens:

1. Log in to [pypi.org](https://pypi.org).
2. Go to **Account Settings** → **Publishing**.
3. Under **Add a new pending publisher**:
   - **PyPI Project Name**: `agent-praxis`
   - **Owner**: `shashikant649sharma`
   - **Repository Name**: `agent-praxis`
   - **Workflow name**: `cd.yml`
   - **Environment name**: `pypi`
4. GitHub Actions will now authenticate via short-lived OpenID Connect (OIDC) tokens with cryptographic provenance.
