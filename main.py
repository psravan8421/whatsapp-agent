"""CLI entry point: load input JSON -> classify messages -> write output.csv.

Usage:
    python main.py input.json
    python main.py input.json --output results.csv
    python main.py input.json --no-llm      # force the offline heuristic
"""

import argparse
import sys

import pandas as pd

from processor import OUTPUT_COLUMNS, process_messages
from utils import get_logger, load_json_file

LOGGER = get_logger("wa_router.main")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WhatsApp Intelligent Notification Router"
    )
    parser.add_argument("input", nargs="?", default="input.json", help="Path to the input JSON file")
    parser.add_argument("-o", "--output", default="output.csv", help="Path to the output CSV file")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the LLM and use the built-in heuristic classifier only",
    )
    return parser.parse_args(argv)


def save_csv(rows, output_path: str) -> pd.DataFrame:
    """Write the classification rows to CSV with a stable column order."""
    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    frame.to_csv(output_path, index=False)
    return frame


def main(argv=None) -> int:
    args = parse_args(argv)

    try:
        payload = load_json_file(args.input)
        rows = process_messages(payload, use_llm=not args.no_llm)
    except (FileNotFoundError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 1

    if not rows:
        LOGGER.error("No messages found in %s", args.input)
        return 1

    frame = save_csv(rows, args.output)
    LOGGER.info("Wrote %s rows to %s", len(frame), args.output)
    LOGGER.info("Action breakdown: %s", frame["action"].value_counts().to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
