import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data = {}

    def load_all(self):
        csv_files = {
            "messages": "messages.csv",
            "users": "users.csv",
            "groups": "groups.csv",
            "business_accounts": "business_accounts.csv",
            "user_business_history": "user_business_history.csv",
            "message_history": "message_history.csv",
            "message_events": "message_events.csv",
            "images": "images.csv",
            "voice_notes": "voice_notes.csv",
            "daily_notification_summary": "daily_notification_summary.csv"
        }
        
        for key, filename in csv_files.items():
            path = self._find_file(filename)
            if path:
                self.data[key] = pd.read_csv(path)
                logger.info(f"Loaded {key} from {path}")
            else:
                self.data[key] = pd.DataFrame()
                logger.warning(f"Could not find {filename} in {self.data_dir}")

    def _find_file(self, filename: str):
        # The attachments are in flat UUID subdirectories, we need to find them
        for path in self.data_dir.rglob(filename):
            return path
        return None

    def get_messages(self):
        return self.data.get("messages", pd.DataFrame())

    def get_context(self):
        return {k: v for k, v in self.data.items() if k != "messages"}
