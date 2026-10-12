# 07 — Auto mode and the Full context fallback

**What to build:** Auto becomes the default Retrieval mode. It estimates the tokens of
the Thread's Documents: 50k or less goes to Full context, and more goes to Agentic
navigation. Auto recalculates after every upload. When Full context is chosen
explicitly and the Documents exceed 100k tokens, it falls back to Agentic navigation
and says so. Every reply shows its Effective mode. See the spec at
`.scratch/pdf-chat/spec.md`.

**Blocked by:** 05 — Agentic navigation

**Status:** ready-for-agent

- [ ] The settings panel has all four Retrieval modes, with Auto as the default.
- [ ] A pure routing function takes the selected Retrieval mode and the Thread's estimated token total, and returns the Effective mode and its label.
- [ ] The labels are, for example, `Mode: Auto → Full context`, `Mode: Auto → Agentic navigation` and `Mode: Full context → Agentic navigation (too large)`. Modes without a redirect show their own name.
- [ ] Auto never picks RAG.
- [ ] Unit tests cover the 50k and 100k boundaries and the labels, plus one `ask` flow each for Auto with a small fixture and with a large fixture.
