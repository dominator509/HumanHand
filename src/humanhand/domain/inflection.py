"""Deterministic, conservative inflection preservation (stdlib only).

This module preserves the inflection of a source word when a lexical
rule replaces its lemma with a target lemma. It is intentionally
mechanical: every rule below is documented, deterministic, and declines
(returns None) on anything it does not recognize, so a caller treats
None as a strict no-op.

Rules (documented, in evaluation order)
---------------------------------------
1. Validity: if any argument is empty, decline (None). A rule without
   a source or target lemma cannot produce a real replacement.

2. Form — the inflected output is the target lemma with the source's
   inflection re-applied:
   a. Base form: when ``source_surface.lower() == source_lemma.lower()``
      the source is the base (uninflected) form, so the output is the
      target lemma unchanged.
   b. ``-ing``: when the lowercased surface ends in ``"ing"`` but the
      lowercased lemma does not, append ``"ing"`` after dropping a final
      silent ``e`` from the target.
   c. ``-ed``: when the lowercased surface ends in ``"ed"`` but the
      lowercased lemma does not, append ``"d"`` to a target ending in
      ``e`` and ``"ed"`` otherwise.
   d. Otherwise decline (None): plurals, comparatives, irregular forms,
      and every other inflection are unsupported and left unchanged.

3. Format — the case of the source surface is re-applied to the
   inflected output:
   a. ALL-CAPS: when the surface has at least one cased character and
      every cased character is uppercase, the output is uppercased.
   b. Title-Case: when the surface has at least one cased character,
      its first cased character is uppercase, and every other cased
      character is lowercase, the output's first character is
      uppercased and the remainder is kept as produced.
   c. Otherwise the output is kept exactly as produced.

Limitations (documented)
------------------------
- The suffix protocol handles only a final silent ``e``. Other stem
  changes and consonant doubling are not modeled and remain subject to
  collocation checks and human review.
- Plurals are unsupported and decline to None.
- Case detection uses ``str.isupper()``/``str.islower()`` (Unicode
  aware); mixed-case words such as ``"iPhone"`` are treated as
  "other" format and passed through unchanged.
"""

from __future__ import annotations

_SUFFIX_ING = "ing"
_SUFFIX_ED = "ed"


def inflect_target(source_surface: str, source_lemma: str, target_lemma: str) -> str | None:
    """Preserve inflection deterministically or decline (None = no-op).

    ``source_surface`` is the word as written, ``source_lemma`` its
    canonical (dictionary) form, and ``target_lemma`` the rule's
    replacement lemma. Returns the inflected target when the source
    inflection is recognized, otherwise None. The full rule list and
    limitations are documented in the module docstring.
    """
    if not source_surface or not source_lemma or not target_lemma:
        return None
    inflected = _inflected_form(source_surface, source_lemma, target_lemma)
    if inflected is None:
        return None
    return _apply_case(source_surface, inflected)


def _inflected_form(source_surface: str, source_lemma: str, target_lemma: str) -> str | None:
    """Base-form or suffix-protocol output; None declines the form."""
    surface_lower = source_surface.lower()
    lemma_lower = source_lemma.lower()
    if surface_lower == lemma_lower:
        return target_lemma
    if surface_lower.endswith(_SUFFIX_ING) and not lemma_lower.endswith(_SUFFIX_ING):
        stem = target_lemma[:-1] if target_lemma.lower().endswith("e") else target_lemma
        return stem + _SUFFIX_ING
    if surface_lower.endswith(_SUFFIX_ED) and not lemma_lower.endswith(_SUFFIX_ED):
        return target_lemma + ("d" if target_lemma.lower().endswith("e") else _SUFFIX_ED)
    return None


def _apply_case(source_surface: str, candidate: str) -> str:
    """Re-apply the source surface's case format to ``candidate``."""
    case_class = _case_class(source_surface)
    if case_class == "all_caps":
        return candidate.upper()
    if case_class == "title_case":
        return candidate[:1].upper() + candidate[1:]
    return candidate


def _case_class(source_surface: str) -> str:
    """One of ``"all_caps"``, ``"title_case"``, or ``"other"`` (deterministic).

    "Title-Case" means: at least one cased character, the FIRST cased
    character uppercase, and every other cased character lowercase.
    "ALL-CAPS" means: at least one cased character and every cased
    character uppercase. A surface with no cased characters is
    "other".
    """
    cased = [char for char in source_surface if char.isupper() or char.islower()]
    if not cased:
        return "other"
    if all(char.isupper() for char in cased):
        return "all_caps"
    if cased[0].isupper() and all(char.islower() for char in cased[1:]):
        return "title_case"
    return "other"


def decline_inflection(source_surface: str) -> str | None:
    """Return a deterministic category tag for a recognized inflection.

    Recognized categories, first match wins:
    - ``"all_caps"`` / ``"title_case"`` (case categories take priority),
    - ``"ing"`` / ``"ed"`` (suffix categories),
    otherwise None (unsupported -> no-op contract).
    """
    if not source_surface:
        return None
    case_class = _case_class(source_surface)
    if case_class != "other":
        return case_class
    surface_lower = source_surface.lower()
    if surface_lower.endswith(_SUFFIX_ING):
        return "ing"
    if surface_lower.endswith(_SUFFIX_ED):
        return "ed"
    return None
