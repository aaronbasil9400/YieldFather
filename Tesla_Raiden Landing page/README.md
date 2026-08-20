# Factory Analytics Hub

Factory Analytics Hub is a local analytics application for Flex / Teradyne production data. It currently contains two Streamlit dashboards:

- **Yield and Defect Analysis**: CSV-based yield, first-pass, defect Pareto, WIP, and trend views.
- **UltraFlexPlus Dragon SPC Dashboard**: TDF-log consolidation into SQLite and interactive measurement/capability analysis.

## Current status

The application is a working Python/Streamlit prototype, **not yet a standalone desktop product**. A user currently needs a compatible Python runtime and the packages in `requirements.txt`; [run.bat](run.bat) only starts Streamlit and does not install or validate those requirements. The portability target and implementation sequence are documented in [docs/PORTABILITY_PLAN.md](docs/PORTABILITY_PLAN.md).

## Documentation map

- [Project scope](docs/PROJECT_SCOPE.md) — what is in scope, inputs, outputs, and boundaries.
- [Architecture](docs/ARCHITECTURE.md) — current components and data flows.
- [Data and KPI contract](docs/DATA_AND_KPIS.md) — required fields and metric definitions.
- [Statistical validation](docs/STATISTICAL_VALIDATION.md) — verified formulas, limitations, and release blockers.
- [Analytics roadmap](docs/ANALYTICS_ROADMAP.md) — planned data contracts, KPI fixes, chart selection, diagnostics, and user insights.
- [Portability plan](docs/PORTABILITY_PLAN.md) — a staged path to no-Python-setup desktop releases.
- [Test strategy](docs/TEST_STRATEGY.md) — regression and release validation.
- [Agent guide](AGENTS.md) and [agent task playbooks](SKILLS.md) — working conventions for future agents.

## Development-only launch

After installing the project dependencies in an isolated environment, start the multipage app with:

```bash
python -m streamlit run Home.py
```

This command is for developers. End users should receive a signed, platform-specific packaged build after the portability plan is implemented.

## Entrypoints

- [Home.py](Home.py) — Streamlit landing page and navigation.
- [Yield_Report.py](Yield_Report.py) — yield dashboard.
- [SPC_DASHBOARD.py](SPC_DASHBOARD.py) — TDF parser, SQLite consolidator, and SPC dashboard.

## Important caveat

Do not use current SPC capability or Yield first-pass/Pareto figures for release or production decisions without addressing the blockers in [docs/STATISTICAL_VALIDATION.md](docs/STATISTICAL_VALIDATION.md). Several formulas are correctly coded, but the current aggregation and labeling can make a mathematically correct calculation answer the wrong business question.
