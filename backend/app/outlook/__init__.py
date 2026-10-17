"""Optional active-event outlook from Cache's model (T050). Owned by Rudra.

Advisory only: it never changes scores, alerts, or the lightning timer.
"""

from app.outlook.context import event_context_from_notice
from app.outlook.service import EventOutlookService, get_event_outlook_service

__all__ = ["EventOutlookService", "event_context_from_notice", "get_event_outlook_service"]
