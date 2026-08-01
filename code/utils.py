import logging
from pathlib import Path

def setup_logging(log_file: Path):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def format_evidence(ids):
    if not ids or len(ids) == 0:
        return "none"
    return ";".join(map(str, ids))
