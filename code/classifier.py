import logging

logger = logging.getLogger(__name__)

class Classifier:
    def classify(self, message, features):
        text = str(message.get('message_text', '')).lower()
        
        # Priority 1: Phishing / Scam
        if (features['has_otp'] and features['has_urgency']) or \
           (features['has_link'] and features['has_urgency'] and not features['business_info'].get('verified', False)):
            return 'scam', 0.95
        
        # Priority 2: Spam
        if features['high_forward_count'] or features['has_greeting'] and features['is_forwarded']:
            return 'spam', 0.85
        
        # Priority 3: Forward
        if features['is_forwarded']:
            return 'forward', 0.80
            
        # Priority 4: Business Update / Promotion
        if features['business_info']:
            if features['has_money'] or features['has_link']:
                return 'promotion', 0.85
            return 'business_update', 0.90

        # Priority 5: Event
        if features['has_event']:
            return 'event', 0.85

        # Priority 6: Payment
        if features['has_money']:
            return 'payment', 0.85

        # Priority 7: Urgent
        if features['has_urgency']:
            return 'urgent', 0.80
            
        # Default: Personal
        return 'personal', 0.75
