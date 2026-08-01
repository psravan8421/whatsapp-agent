import os
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "dataset"
DEFAULT_OUTPUT_FILE = DEFAULT_DATA_DIR / "output.csv"
LOG_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
LOG_DIR.mkdir(exist_ok=True)

# LLM / Classification Config
TEMPERATURE = 0.3
CONFIDENCE_THRESHOLD = 0.7

# GitHub Config
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_URL = "https://github.com/psravan8421/whatsapp-agent.git"
