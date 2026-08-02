import argparse
import logging
from pathlib import Path
import pandas as pd
import sys

# Add current dir to path to import local modules
sys.path.append(str(Path(__file__).parent))

import config
from data_loader import DataLoader
from feature_engineering import FeatureEngineer
from classifier import Classifier
from decision_engine import DecisionEngine
from evidence_engine import EvidenceEngine
from github_handler import GitHubHandler
from utils import setup_logging, format_evidence

logger = logging.getLogger("main")

def main():
    parser = argparse.ArgumentParser(description="WhatsApp AI Message Router")
    parser.add_argument("--data_dir", type=str, default=str(config.DEFAULT_DATA_DIR),
                        help="Directory containing the datasets")
    parser.add_argument("--output", type=str, help="Path to save the output CSV")
    parser.add_argument("--push", action="store_true", help="Push results to GitHub")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_file = Path(args.output) if args.output else data_dir / "router_output.csv"
    
    log_file = config.LOG_DIR / "output.log"
    setup_logging(log_file)

    logger.info("Starting WhatsApp AI Message Router...")

    # Load data
    loader = DataLoader(data_dir)
    loader.load_all()
    messages = loader.get_messages()
    context = loader.get_context()

    if messages.empty:
        logger.error("No messages found to process.")
        sys.exit(1)

    # Initialize engines
    fe = FeatureEngineer(context)
    clf = Classifier()
    de = DecisionEngine()
    ee = EvidenceEngine(context)

    results = []
    
    # Classification summary
    summary = {}

    logger.info(f"Processing {len(messages)} messages...")
    
    for _, msg in messages.iterrows():
        msg_dict = msg.to_dict()
        features = fe.extract_features(msg_dict)
        m_type, confidence = clf.classify(msg_dict, features)
        action, reason = de.decide(msg_dict, m_type, confidence, features)
        evidence = ee.get_evidence(msg_dict)
        
        results.append({
            "message_id": msg_dict.get("message_id"),
            "action": action,
            "message_type": m_type,
            "reason": reason,
            "confidence": confidence,
            "evidence_message_ids": format_evidence(evidence)
        })
        
        summary[m_type] = summary.get(m_type, 0) + 1

    # Save output
    output_df = pd.DataFrame(results)
    output_df.to_csv(output_file, index=False)
    logger.info(f"Generated {output_file.name} with {len(results)} rows.")

    # GitHub Sync
    sync_status = False
    if args.push:
        gh = GitHubHandler(config.REPO_URL, config.GITHUB_TOKEN)
        sync_status = gh.sync(output_file)
    else:
        logger.info("GitHub push skipped (use --push to enable).")

    # Print Console Output as required
    print("-" * 30)
    print("WhatsApp AI Message Router Execution Summary")
    print("-" * 30)
    print(f"Total messages processed: {len(results)}")
    print("Classification summary:")
    for m_type, count in summary.items():
        print(f"  - {m_type}: {count}")
    print(f"GitHub update status: {'Success' if sync_status else 'Skipped/Failed'}")
    print("Execution success message: Pipeline completed successfully.")
    print("-" * 30)

if __name__ == "__main__":
    main()
