import pandas as pd
import logging

logger = logging.getLogger(__name__)

class EvidenceEngine:
    def __init__(self, context):
        self.context = context

    def get_evidence(self, message):
        user_id = message.get('user_id')
        message_id = message.get('message_id')
        
        history = self.context.get('message_history', pd.DataFrame())
        events = self.context.get('message_events', pd.DataFrame())
        
        if history.empty:
            return []

        # Find history for this user
        user_history = history[history['user_id'] == user_id]
        
        # Simple evidence: last 2 messages from history for this user
        evidence_ids = user_history.tail(2)['message_id'].tolist()
        
        # Check events to see if they were ignored/replied
        if not events.empty:
            for eid in evidence_ids:
                event = events[events['message_id'] == eid]
                if not event.empty:
                    # Could add logic to weigh evidence based on event
                    pass
        
        return [eid for eid in evidence_ids if eid != message_id]
