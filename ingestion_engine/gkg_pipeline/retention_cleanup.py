import argparse
import json
import re
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

import duckdb
import pandas as pd
import yaml


GKG_COLS = [
    "gkgrecordid",
    "date",
    "sourcecollectionidentifier",
    "sourcecommonname",
    "documentidentifier",
    "counts",
    "v2counts",
    "themes",
    "v2themes",
    "locations",
    "v2locations",
    "persons",
    "v2persons",
    "organizations",
    "v2organizations",
    "v2tone",
    "dates",
    "gcam",
    "sharingimage",
    "relatedimages",
    "socialimageembeds",
    "socialvideoembeds",
    "quotations",
    "allnames",
    "amounts",
    "translationinfo",
    "extras",
]

GKGCOUNTS_COLS = [
    "date",
    "num_sources",
    "count_type",
    "number",
    "object_type",
    "geo_type",
    "country",
    "adm1",
    "lat",
    "lon",
    "geo_id",
    "urls",
]

PARQUET_ENGINE = "pyarrow"
PARQUET_COMPRESSION = "zstd"


def parse_args():
    parser = argparse.ArgumentParser(description="GDELT retention cleanup")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--apply", action="store_true", help="Apply deletions (default is dry-run)")
    parser.add_argument("--vacuum", action="store_true", help="Vacuum DuckDB after cleanup")
    return parser.parse_args()


def load_config(config_path: str | None):
    if config_path is None:
        config_path = Path(__file__).with_name('config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def parquet_available():
    try:
        __import__(PARQUET_ENGINE)
        return True
    except Exception:
        return False


def parse_date_from_name(name: str):
    # 15-min GKG: YYYYMMDDHHMMSS.gkg.csv
    m = re.match(r'^(\d{14})\.gkg\.csv$', name)
    if m:
        return datetime.strptime(m.group(1), '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)

    # Daily counts: YYYYMMDD.gkgcounts.csv
    m = re.match(r'^(\d{8})\.gkgcounts\.csv$', name)
    if m:
        return datetime.strptime(m.group(1), '%Y%m%d').replace(tzinfo=timezone.utc)

    # Processed: gdelt_metrics_YYYYMMDD.csv or gdelt_admin1_metrics_YYYYMMDD.csv
    m = re.match(r'^gdelt_(metrics|admin1_metrics)_(\d{8})\.csv$', name)
    if m:
        return datetime.strptime(m.group(2), '%Y%m%d').replace(tzinfo=timezone.utc)

    return None


def get_dir_size(path: Path):
    if not path.exists():
        return 0
    total = 0
    for file in path.rglob('*'):
        if file.is_file():
            total += file.stat().st_size
    return total


def count_files(path: Path):
    if not path.exists():
        return 0
    return sum(1 for p in path.rglob('*') if p.is_file())


def collect_candidates(path: Path, cutoff: datetime):
    candidates = []
    if not path.exists():
        return candidates
    for file in path.iterdir():
        if not file.is_file():
            continue
        file_date = parse_date_from_name(file.name)
        if file_date and file_date < cutoff:
            candidates.append((file, file_date))
    return candidates


def archive_path_for(file: Path, file_date: datetime, file_kind: str, archive_root: Path):
    subdir = archive_root / file_kind / file_date.strftime('%Y/%m/%d')
    subdir.mkdir(parents=True, exist_ok=True)
    base = file.name
    if base.endswith('.csv'):
        base = base[:-4]
    return subdir / f"{base}.parquet"


def load_dataframe_for_archive(file: Path, file_kind: str):
    if file_kind == 'raw_gkg':
        return pd.read_csv(
            file,
            sep='\t',
            header=None,
            names=GKG_COLS,
            dtype=str,
            low_memory=False
        )
    if file_kind == 'raw_gkgcounts':
        return pd.read_csv(
            file,
            sep='\t',
            header=None,
            names=GKGCOUNTS_COLS,
            dtype=str,
            low_memory=False
        )
    # processed
    return pd.read_csv(file, low_memory=False)


def archive_file(file: Path, file_date: datetime, file_kind: str, archive_root: Path):
    if not parquet_available():
        return None, "pyarrow not installed"
    out_path = archive_path_for(file, file_date, file_kind, archive_root)
    if out_path.exists():
        return out_path, None

    df = load_dataframe_for_archive(file, file_kind)
    df.to_parquet(
        out_path,
        index=False,
        engine=PARQUET_ENGINE,
        compression=PARQUET_COMPRESSION
    )
    return out_path, None


def cleanup_files(
    file_kind: str,
    source_dir: Path,
    cutoff: datetime,
    archive_root: Path,
    apply: bool
):
    results = {
        "candidates": 0,
        "archived": 0,
        "deleted": 0,
        "skipped": 0,
        "raw_bytes": 0,
        "archive_bytes": 0,
        "errors": [],
    }

    candidates = collect_candidates(source_dir, cutoff)
    results["candidates"] = len(candidates)

    for file, file_date in candidates:
        results["raw_bytes"] += file.stat().st_size
        try:
            archive_path, error = archive_file(file, file_date, file_kind, archive_root)
            if error:
                results["skipped"] += 1
                results["errors"].append({"file": str(file), "error": error})
                continue
            results["archived"] += 1
            if archive_path and archive_path.exists():
                results["archive_bytes"] += archive_path.stat().st_size

            if apply:
                file.unlink(missing_ok=True)
                results["deleted"] += 1
        except Exception as exc:
            results["skipped"] += 1
            results["errors"].append({"file": str(file), "error": str(exc)})

    return results


def cleanup_duckdb(db_path: Path, cutoff_date: date, apply: bool):
    result = {
        "exists": False,
        "cutoff_date": cutoff_date.isoformat(),
        "gdelt_metrics": {},
        "gdelt_admin1_metrics": {},
    }
    if not db_path.exists():
        return result

    result["exists"] = True
    con = duckdb.connect(str(db_path))
    for table in ["gdelt_metrics", "gdelt_admin1_metrics"]:
        total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        old = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE date < ?",
            [cutoff_date]
        ).fetchone()[0]
        deleted = 0
        if apply and old > 0:
            con.execute(f"DELETE FROM {table} WHERE date < ?", [cutoff_date])
            deleted = old
        remaining = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        result[table] = {
            "total": int(total),
            "older_than_cutoff": int(old),
            "deleted": int(deleted),
            "remaining": int(remaining),
        }
    con.close()
    return result


def write_report(report_dir: Path, report: dict):
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    report_path = report_dir / f"retention_report_{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    return report_path


def run_retention(config_path: str | None = None, apply: bool = False, vacuum: bool = False):
    start_time = time.time()
    config = load_config(config_path)

    retention = config.get('retention', {})
    raw_gkg_days = int(retention.get('raw_gkg_days', 7))
    raw_counts_days = int(retention.get('raw_gkgcounts_days', 90))
    processed_days = int(retention.get('processed_days', 365))

    now = datetime.now(timezone.utc)
    raw_gkg_cutoff = now - timedelta(days=raw_gkg_days)
    raw_counts_cutoff = now - timedelta(days=raw_counts_days)
    processed_cutoff = now - timedelta(days=processed_days)

    paths = config['paths']
    raw_gkg_dir = Path(paths['raw_gkg_dir'])
    raw_counts_dir = Path(paths['raw_gkgcounts_dir'])
    processed_dir = Path(paths['processed_dir'])
    archive_root = Path(paths.get('archive_dir', 'data/archive/gkg'))
    db_path = Path(paths['db_path'])

    size_before = {
        "raw_gkg_dir": get_dir_size(raw_gkg_dir),
        "raw_gkgcounts_dir": get_dir_size(raw_counts_dir),
        "processed_dir": get_dir_size(processed_dir),
        "archive_dir": get_dir_size(archive_root),
        "duckdb": db_path.stat().st_size if db_path.exists() else 0,
    }

    file_counts_before = {
        "raw_gkg_dir": count_files(raw_gkg_dir),
        "raw_gkgcounts_dir": count_files(raw_counts_dir),
        "processed_dir": count_files(processed_dir),
        "archive_dir": count_files(archive_root),
    }

    raw_gkg_results = cleanup_files(
        "raw_gkg",
        raw_gkg_dir,
        raw_gkg_cutoff,
        archive_root,
        apply
    )
    raw_counts_results = cleanup_files(
        "raw_gkgcounts",
        raw_counts_dir,
        raw_counts_cutoff,
        archive_root,
        apply
    )
    processed_results = cleanup_files(
        "processed",
        processed_dir,
        processed_cutoff,
        archive_root,
        apply
    )

    db_results = cleanup_duckdb(db_path, processed_cutoff.date(), apply)

    if apply and vacuum and db_path.exists():
        con = duckdb.connect(str(db_path))
        con.execute("VACUUM")
        con.close()

    size_after = {
        "raw_gkg_dir": get_dir_size(raw_gkg_dir),
        "raw_gkgcounts_dir": get_dir_size(raw_counts_dir),
        "processed_dir": get_dir_size(processed_dir),
        "archive_dir": get_dir_size(archive_root),
        "duckdb": db_path.stat().st_size if db_path.exists() else 0,
    }

    file_counts_after = {
        "raw_gkg_dir": count_files(raw_gkg_dir),
        "raw_gkgcounts_dir": count_files(raw_counts_dir),
        "processed_dir": count_files(processed_dir),
        "archive_dir": count_files(archive_root),
    }

    report = {
        "timestamp_utc": now.isoformat(),
        "mode": "APPLY" if apply else "DRY_RUN",
        "retention_days": {
            "raw_gkg_days": raw_gkg_days,
            "raw_gkgcounts_days": raw_counts_days,
            "processed_days": processed_days,
        },
        "archive_layout": "archive_dir/{file_kind}/YYYY/MM/DD/{basename}.parquet",
        "parquet": {
            "engine": PARQUET_ENGINE,
            "compression": PARQUET_COMPRESSION,
            "available": parquet_available(),
        },
        "sizes_before_bytes": size_before,
        "sizes_after_bytes": size_after,
        "file_counts_before": file_counts_before,
        "file_counts_after": file_counts_after,
        "files": {
            "raw_gkg": raw_gkg_results,
            "raw_gkgcounts": raw_counts_results,
            "processed": processed_results,
        },
        "duckdb": db_results,
        "elapsed_seconds": round(time.time() - start_time, 2),
    }

    report_path = write_report(Path("logs/retention"), report)

    print("=== Retention Cleanup ===")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Raw GKG (> {raw_gkg_days} days): {raw_gkg_results['candidates']} candidates")
    print(f"Raw GKGCounts (> {raw_counts_days} days): {raw_counts_results['candidates']} candidates")
    print(f"Processed (> {processed_days} days): {processed_results['candidates']} candidates")
    print(f"Report: {report_path}")

    return report


def main():
    args = parse_args()
    run_retention(config_path=args.config, apply=args.apply, vacuum=args.vacuum)


if __name__ == '__main__':
    main()
