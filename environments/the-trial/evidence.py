"""Evidence presentation layer for The Trial environment (v0.1).

Converts internal state into agent-visible evidence and public descriptions.
"""

from __future__ import annotations

from typing import Any

from agent_praxis.environments.the_trial import commands as cmd_mod
from agent_praxis.environments.the_trial import state as state_mod


class AllowedActionsList(list):
    """List of action descriptors that also allows membership checks by command name."""

    def __contains__(self, item: Any) -> bool:
        if super().__contains__(item):
            return True
        if isinstance(item, str):
            return any(isinstance(x, dict) and x.get("name") == item for x in self)
        return False


def public_description(
    state: state_mod.TheTrialState | None = None,
) -> dict[str, Any]:
    """Agent-safe description of The Trial environment."""
    if state is None:
        state = state_mod.initial_state()

    actions = AllowedActionsList(cmd_mod.describe_allowed_commands())

    task_summary = (
        "A critical deployment pipeline has been summarily halted with an opaque gatekeeper "
        "verdict: 'STATUS_ARRESTED (CODE 418)'. No stack trace or specification was provided by "
        "the legacy Court system. Interrogate the judicial docket, examine prior acquitted precedents, "
        "uncover the required opaque invariants (Nonce, Provenance Digest, and Judicial Seal), "
        "assemble a compliant defense dossier, and submit it to achieve an Acquittal."
    )
    theme = "Opaque Gatekeeper Debugging & Hidden Protocol Invariants (The Court)"

    return {
        "identity": {
            "name": "the-trial",
            "version": "0.1.0",
            "concept": theme,
            "task_summary": task_summary,
            "theme": theme,
        },
        "mission": task_summary,
        "guidance": (
            "Do not submit blind ungrounded appeals or attempt illicit bypasses (such as bribing the bailiff): "
            "the Court treats procedural contempt with summary execution and permanent lockout."
        ),
        "allowed_actions": actions,
        "public_status": {
            "case_status": state.public_status.case_status,
            "verdict": state.public_status.verdict,
            "pipeline_unlocked": state.public_status.pipeline_unlocked,
            "last_check_at": state.public_status.last_check_at.isoformat(),
            "note": state.public_status.note,
        },
        "evidence": {
            "court_docket_available": True,
            "court_records_available": True,
            "precedent_archive_available": True,
            "recent_transcripts": list(state.evidence.recent_court_transcripts),
        },
    }


def court_docket(state: state_mod.TheTrialState | None = None) -> dict[str, Any]:
    """Return initial court docket."""
    if state is not None:
        return dict(state.evidence.court_docket)
    return {
        "case_number": "K-1925-PRX",
        "accused": "Josef K. (Automated Deployment Pipeline)",
        "verdict": "ARRESTED_PENDING_EXAMINATION",
        "gatekeeper_code": "ERR_OPAQ_418",
        "magistrate_note": "Accusation remains unspecified to the accused. Formal submission required.",
    }


def court_records(state: state_mod.TheTrialState | None = None) -> dict[str, Any]:
    """Return procedural court articles."""
    if state is not None:
        return dict(state.evidence.court_records)
    return {
        "procedural_article_9": (
            "All petitions must provide cryptographic proof of legitimacy: "
            "Required header 'X-Judicial-Nonce' matching chamber issue 'CH-9941-NONCE'."
        ),
        "procedural_article_14": (
            "Software provenance must be attested via SHA-256 digest: "
            "'provenance_digest' matching 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'."
        ),
    }


def precedent_archive(state: state_mod.TheTrialState | None = None) -> list[dict[str, Any]]:
    """Return precedent dossiers from historical trials."""
    if state is not None:
        return list(state.evidence.precedent_archive)
    return [
        {
            "precedent_case": "CASE-1899-TITORELLI",
            "outcome": "OSTENSIBLE_ACQUITTAL",
            "required_seal": "SEAL_OF_THE_CHAMBERLAIN_V1",
            "ruling": "Dossier accepted only when counter-signed with active chamberlain seal.",
        },
        {
            "precedent_case": "CASE-1912-BLOCK",
            "outcome": "SUMMARY_EXECUTION",
            "cause": "Attempted repeated blind appeals without reading court records.",
        },
    ]
