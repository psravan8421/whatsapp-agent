import logging

logger = logging.getLogger(__name__)

class DecisionEngine:
    def decide(self, message, m_type, confidence, features):
        # Mute logic
        if m_type in ['spam', 'scam']:
            return 'mute', "Detected potential " + m_type
            
        # Notify logic
        if m_type == 'urgent':
            return 'notify', "Urgent message detected"
        
        if m_type == 'personal' and features['user_info'].get('messages_replied_30d', 0) > 5:
             return 'notify', "Frequent personal contact"
             
        if features['business_info'].get('verified') and m_type == 'business_update':
            return 'notify', "Verified business update"
            
        if features['has_event']:
            return 'notify', "Event related message"
            
        # Digest logic
        if m_type in ['promotion', 'forward']:
            return 'digest', "Non-urgent " + m_type
            
        return 'digest', "Default to digest for regular updates"
