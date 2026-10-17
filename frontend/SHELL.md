# PlanIT Control frontend

The T030 responsive shell now hosts Cache's T031-T038 crew/supervisor application. Nick's earlier attribution and shell PR #16 are preserved. Cache owns remaining frontend implementation; Auth0 internals remain Braydin's and canonical API contracts remain Rudra's.

From the repository root, with Node 24 on PATH:

```powershell
cd frontend
npm ci
npm run dev -- --host localhost --port 5173 --strictPort
```

Open http://localhost:5173/. The default is an explicitly simulated, interactive demo without Auth0, Tiger Data, credentials or backend writes. It includes crew reports/acknowledgements, supervisor review/confirmation/instructions, 55 map/list locations and two exact-site research advisories. Local demo state persists in one browser namespace; selected photos stay in memory only. This is not real authentication, live monitoring or work authorization.

See [INTEGRATION.md](INTEGRATION.md) for the guided workflow, real API configuration, precise service blockers, architecture, fixture provenance and checks. [Integration status](../docs/INTEGRATION_STATUS.md) records each task's acceptance; [redesign handoff](../docs/FRONTEND_REDESIGN_HANDOFF.md) identifies presentation boundaries. The former shell-only unavailable destinations have been replaced; historical T030 evidence remains in `docs/t030-acceptance.json`.
