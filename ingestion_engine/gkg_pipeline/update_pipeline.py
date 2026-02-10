import argparse
from datetime import datetime
from pathlib import Path

from fetch_gdelt import GDELTFetcher
from process_data import DataProcessor
from retention_cleanup import run_retention


def parse_args():
    parser = argparse.ArgumentParser(description="GKG pipeline update")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--retention", action="store_true", help="Run retention cleanup after update (dry-run)")
    parser.add_argument("--retention-apply", action="store_true", help="Apply retention deletions")
    parser.add_argument("--vacuum", action="store_true", help="Vacuum DuckDB after retention")
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"=== GKG Pipeline Update: {datetime.now()} ===")
    fetcher = GDELTFetcher(args.config)
    processor = DataProcessor(args.config)

    # 1. Fetch latest 15-min GKG file (raw archive)
    try:
        gkg_path = fetcher.fetch_latest_15min()
        print(f"Saved 15-min GKG: {gkg_path}")
    except Exception as e:
        print(f"15-min GKG fetch failed: {e}")

    # 2. Fetch daily counts (yesterday)
    try:
        counts_path = fetcher.fetch_daily_counts()
        print(f"Saved daily counts: {counts_path}")
    except Exception as e:
        print(f"Daily counts fetch failed: {e}")
        counts_path = None

    # 3. Process counts into metrics DB
    if counts_path:
        result = processor.process_gdelt_counts(counts_path)
        if result:
            print(f"Processed counts: {result}")

    # 4. Produce summary output (last 30 days)
    summary = processor.get_daily_summary(days=30)
    out_path = Path(processor.processed_dir) / 'gdelt_daily_summary.csv'
    summary.to_csv(out_path, index=False)
    print(f"Saved summary: {out_path} ({len(summary)} rows)")

    if args.retention:
        run_retention(
            config_path=args.config,
            apply=args.retention_apply,
            vacuum=args.vacuum
        )

    print("=== Update Complete ===")


if __name__ == '__main__':
    main()
