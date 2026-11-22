import Sejmbench.SeedRule
namespace Sejmbench
example (r : Record) (d : Division) (h : IsTrack d r.club) (hy : isYesKind r.kind = true) :
    seedYes (r :: d) = seedYes d + 1 ∧ seedNo (r :: d) = seedNo d := by
  obtain ⟨h1, h2, _⟩ := seed_cons_of_track r d h
  rw [hy] at h1
  simp at h1 h2
  exact ⟨h1, by omega⟩
end Sejmbench
