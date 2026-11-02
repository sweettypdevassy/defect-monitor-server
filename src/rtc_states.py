"""
RTC workflow state helpers (no heavy dependencies, safe to import from scripts).
"""

from typing import Optional


def closed_state_label(state_url: str) -> Optional[str]:
    """
    Return a human-readable label if the RTC state URL is a closed-type state
    (Canceled / Closed / Resolved / Closed (GHE)), otherwise None.
    """
    if not state_url or 'jazz/oslc/workflows' not in state_url:
        return None

    s = state_url.lower()
    if 'defect_workflow.state.s2' in s:
        return 'Closed (GHE)'
    if 'canceled' in s or 'cancelled' in s:
        return 'Canceled'
    if 'closed' in s:
        return 'Closed'
    if 'resolved' in s:
        return 'Resolved'
    return None
