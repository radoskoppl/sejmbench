# Data licence and provenance

The MIT licence of this repository covers **code only**. It does not licence
the data.

## Sejm data

- Fixtures and the mirror derive exclusively from the official Sejm API
  (api.sejm.gov.pl). Each fixture pins the sha256 of the source record and
  carries a provenance URL.
- The published mirror (`patrykorwat/sejm-votings` on Hugging Face) states
  its own licence and provenance in the dataset card; that licence governs
  the dataset, not this file.

## Third-party text

No third-party text (category exports, scraped posts, press material) enters
fixtures without a per-source licence and personal-data audit. Social-media
posts are out of scope for fixture corpora (copyright, personal data,
selection bias).

## Personal data

Roll-call records (names, clubs, votes) are public official records. They
are reproduced verbatim for verification; enrichment with non-public data is
not permitted.
