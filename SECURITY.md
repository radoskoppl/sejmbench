# Security policy

## Reporting

Report vulnerabilities via GitHub private security advisories (the Security
tab) or a confidential issue. Response target: 7 days. Do not include
secrets in reports.

## Practices

- No secrets live in the repository; tokens live outside the repo with
  0600 permissions.
- CI workflows run with minimal permissions.
- Content under `results/` is untrusted: it is parsed with fixed rules and
  never executed; result PRs are validated by CI before merge.
- Supported version: `main` only.
