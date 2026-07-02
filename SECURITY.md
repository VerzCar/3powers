# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions, or pull
requests.**

Instead, report them privately through GitHub's **private vulnerability reporting**:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Fill in the advisory form with as much detail as you can.

If private reporting is unavailable to you, contact a maintainer listed in [GOVERNANCE.md](GOVERNANCE.md)
and ask for a private channel before sharing details.

Please include, where possible:

- A description of the issue and its impact.
- Steps to reproduce (a proof of concept, if you have one).
- Affected version, commit, or component.
- Any suggested remediation.

## What to expect

This is a young, community-maintained project, so responses are best-effort:

- We aim to **acknowledge** a report within a few business days.
- We'll work with you to understand and validate the issue, agree on a fix, and coordinate disclosure.
- We'll credit you in the advisory unless you'd prefer to remain anonymous.

## Scope notes specific to 3Powers

3Powers is a trust tool, so a few things are worth calling out:

- **Signing keys.** The trust spine signs the ledger with an Ed25519 key whose **private half must live
  outside the repository** (`3pwr keygen` writes it to `~/.config/3powers/` by default; only the public key
  is committed). Never commit a private signing key. A leaked private key undermines the ledger's
  tamper-evidence and should be treated as a security incident — rotate it.
- **Tamper-evidence, not tamper-proofing.** The ledger and build provenance make tampering *detectable*
  offline via `3pwr verify`; they do not physically prevent a local actor from bypassing enforcement. That
  is by design. The **[threat model](docs/threat-model.md)** states exactly what each mechanism proves,
  which tamper classes `verify` detects, and which residuals remain. Reports of ways to tamper *without*
  detection are in scope and valued.
- **Supply chain.** The engine and the sample rely on third-party tools and packages. Vulnerabilities in
  our own code or in how we invoke those tools are in scope; please report upstream issues to the
  respective projects.

## Supported versions

3Powers is pre-1.0 and evolving. Security fixes target the latest `main`. Once tagged releases exist, this
section will list the supported version ranges.
