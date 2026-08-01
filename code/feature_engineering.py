import pandas as pd
import re
import logging

logger = logging.getLogger(__name__)

class FeatureEngineer:
    def __init__(self, context):
        self.context = context

    def extract_features(self, message):
        text = str(message.get('message_text', '')).lower()
        
        features = {
            'has_otp': bool(re.search(r'\botp\b|\bcode\b|\bverification\b', text)),
            'has_urgency': bool(re.search(r'\burgent\b|\bimmediately\b|\baction required\b|\bexpire\b', text)),
            'has_link': bool(re.search(r'https?://\S+|www\.\S+', text)),
            'is_forwarded': message.get('forwarded_count', 0) > 0,
            'high_forward_count': message.get('forwarded_count', 0) >= 5,
            'has_money': bool(re.search(r'\bpay\b|\bamount\b|\bmoney\b|\b₹\b|\b\$\b|\bprice\b', text)),
            'has_greeting': bool(re.search(r'\bhi\b|\bhello\b|\bgood morning\b|\bgood evening\b', text)),
            'has_event': bool(re.search(r'\bmeeting\b|\bevent\b|\bstandup\b|\bstand-up\b|\bcalendar\b|\bdate\b', text)),
        }
        
        # Link context
        user_id = message.get('user_id')
        business_id = message.get('business_id')
        group_id = message.get('group_id')
        
        features['user_info'] = self._get_user_info(user_id)
        features['business_info'] = self._get_business_info(business_id)
        features['group_info'] = self._get_group_info(group_id)
        
        return features

    def _get_user_info(self, user_id):
        users = self.context.get('users', pd.DataFrame())
        if not users.empty and user_id in users['user_id'].values:
            return users[users['user_id'] == user_id].iloc[0].to_dict()
        return {}

    def _get_business_info(self, business_id):
        biz = self.context.get('business_accounts', pd.DataFrame())
        if not biz.empty and business_id and business_id in biz['business_id'].values:
            return biz[biz['business_id'] == business_id].iloc[0].to_dict()
        return {}

    def _get_group_info(self, group_id):
        groups = self.context.get('groups', pd.DataFrame())
        if not groups.empty and group_id and group_id in groups['group_id'].values:
            return groups[groups['group_id'] == group_id].iloc[0].to_dict()
        return {}
