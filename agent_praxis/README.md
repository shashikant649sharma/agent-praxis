# Agent Praxis Package Architecture

The canonical implementation of Agent Praxis is organized under this package root (`agent_praxis/`):
- `environments/`: The 10 adversarial environment implementations, deterministic state models, evidence modules, and command allowlists.
- `framework/`: Evaluation schema (`RunResult`, scoring weights, rubric calculation), Gymnasium wrappers, and parameterized variant managers.
- `commands/`: CLI interface commands and validation runners.
- `client.py`: The lightweight agent-facing HTTP SDK.
- `server.py`: The isolated evaluator server exposing safe actions and finalization over HTTP.

The repository root `README.md` is the primary and authoritative source of truth for benchmark methodology, environment specifications, scoring rubrics, and published results.
