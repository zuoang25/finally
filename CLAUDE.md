# FinAlly Project - the Finance Ally

All project documentation is in the `planning` directory.

The platform is **complete and verified**: backend, frontend, database, LLM chat, Docker
packaging and an end-to-end Playwright suite. `planning/BUILD_SUMMARY.md` is the fastest way in —
read it first. `planning/CONTRACTS.md` is the authoritative interface contract (database surface,
HTTP shapes, LLM service protocol, frontend `data-testid` list); treat it as frozen and update it
deliberately if an interface genuinely changes. `planning/STATUS.md` holds the per-component build
log, and the market data component is summarized in `planning/MARKET_DATA_SUMMARY.md` with more
detail in `planning/archive`. Consult these docs only when required.

The key specification document is PLAN.md, included in full below.

@planning/PLAN.md
