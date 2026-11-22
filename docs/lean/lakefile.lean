import Lake
open Lake DSL

/-- Machine-checked seed-rule spec (CODEBOOK §1–§4). Core Lean only —
no Mathlib, no external dependencies; `lake build` after `elan` installs
the pinned toolchain. -/
package «sejmbench_lean» where

@[default_target]
lean_lib «Sejmbench» where
