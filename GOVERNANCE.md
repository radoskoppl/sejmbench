# Governance

SejmBench is maintained by a single maintainer. These rules make the
benchmark auditable despite that.

## Normative documents

- `CODEBOOK.md` is the contract. Metric definitions change only via a
  version bump, and scores are never compared across metric versions.
- `AGENTS.md` binds automated contributors (results-only PRs, temperature 0,
  no tools). It does not replace this document.

## Errata policy

Ground-truth bugs are fixed by versioned correction, never by silent edits:

1. Open an issue describing the wrong fixture, label, or definition.
2. The fix lands as a CODEBOOK version bump, or as a fixture correction
   recorded in `fixtures/manifest.json` with a new sha256 and a changelog
   entry.
3. Results computed against the affected version are marked non-comparable.

## Conflict of interest

The maintainer's own model may appear on the leaderboard, under the same
rules as everyone else:

- the row is flagged `maintainer`,
- it is produced by the same harness and validated by the same CI,
- the run log (model id, date, prompt hash, output hash) is public.

## Appeals

Dispute a score or a definition by opening an issue. The resolution is
recorded in the issue thread; accepted corrections follow the errata policy.

## Conduct

Be precise, be civil, no partisan framing. The benchmark measures
understanding of decisions, not politics.
