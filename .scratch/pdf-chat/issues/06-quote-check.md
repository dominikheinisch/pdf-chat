# 06 — Quote check for agent answers

**What to build:** Before the Sources list of an Agentic navigation answer is shown,
every quote in the answer is checked against the stored Page text. A quote found on a
different Page than the one cited has its Citation corrected. A quote that isn't found
anywhere is flagged ⚠️ "not found in <name>". See the spec at
`.scratch/pdf-chat/spec.md`.

**Blocked by:** 05 — Agentic navigation

**Status:** ready-for-agent

- [ ] A quote is any text in double quotes of at least 5 words. Shorter quoted text is ignored.
- [ ] Before matching, both sides are normalised: whitespace collapsed, case ignored, words split by a hyphen at a line break joined, ligatures unfolded.
- [ ] The quote is searched for on the cited Page first, then in the whole Document.
- [ ] A match on another Page corrects the Citation and its Sources entry.
- [ ] No match adds the ⚠️ flag to that Sources entry.
- [ ] Unit tests on the pure module cover an exact match, a match only after normalisation, a corrected Page, a flagged quote, and a short quote that is ignored.
