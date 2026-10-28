# AGENTS.md

If you are an AI agent (or a human acting as one) submitting to SejmBench:

1. Read `CODEBOOK.md` first — it is the contract; your score is graded
   against it.
2. Evaluation: temperature 0, no tools, no network, single response, using the
   reference prompt in CODEBOOK §5.
3. Commit your submission under `results/` as:
   `results/<model-name>-<YYYYMMDD>.json` containing:
   ```json
   {
     "model": "<name and version>",
     "date": "<UTC date>",
     "temperature": 0,
     "prompt_hash": "<sha256 of the exact prompt bytes (CODEBOOK section 9.3)>",
     "declared_cutoff": "<model training-cutoff date, or \"unknown\">",
     "raw_output": { "...": "the verbatim parsed JSON from the model" },
     "fixture": "<fixture filename>"
   }
   ```
   One file per fixture, one PR per model.
4. Do not modify `fixtures/`, `seed_rule.py`, or `tests/` in the same PR as
   your result — results-only PRs get reviewed first.
5. If you believe the spec is wrong, open an issue instead of silently
   deviating; deviations are rejected, arguments get heard.
