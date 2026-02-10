import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
import yaml


class GDELTFetcher:
    def __init__(self, config_path: str = None):
        config_path = config_path or Path(__file__).with_name('config.yaml')
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.base_url = self.config['gdelt']['base_url']
        self.gkg_counts_url = self.config['gdelt']['gkg_counts_url']
        self.raw_gkg_dir = Path(self.config['paths']['raw_gkg_dir'])
        self.raw_counts_dir = Path(self.config['paths']['raw_gkgcounts_dir'])
        self.raw_gkg_dir.mkdir(parents=True, exist_ok=True)
        self.raw_counts_dir.mkdir(parents=True, exist_ok=True)

    def _download_zip(self, url: str):
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return zipfile.ZipFile(io.BytesIO(response.content))

    def fetch_latest_15min(self):
        """Fetch latest 15-min GKG file from lastupdate.txt"""
        lastupdate_url = f"{self.base_url}/lastupdate.txt"
        resp = requests.get(lastupdate_url, timeout=30)
        resp.raise_for_status()

        gkg_url = None
        for line in resp.text.splitlines():
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            url = parts[2]
            url_lower = url.lower()
            if 'gkg.csv.zip' in url_lower:
                gkg_url = url
                break

        if not gkg_url:
            raise RuntimeError("Could not locate gkg.csv.zip in lastupdate.txt")

        with self._download_zip(gkg_url) as z:
            csv_name = z.namelist()[0]
            out_path = self.raw_gkg_dir / csv_name
            with z.open(csv_name) as f_in, open(out_path, 'wb') as f_out:
                f_out.write(f_in.read())

        return out_path

    def fetch_daily_counts(self, date: datetime | None = None):
        """Fetch daily gkgcounts file (yesterday by default)"""
        if date is None:
            date = datetime.now(timezone.utc) - timedelta(days=1)

        date_str = date.strftime('%Y%m%d')
        zip_url = f"{self.gkg_counts_url}/{date_str}.gkgcounts.csv.zip"
        csv_url = f"{self.gkg_counts_url}/{date_str}.gkgcounts.csv"

        try:
            with self._download_zip(zip_url) as z:
                csv_name = z.namelist()[0]
                out_path = self.raw_counts_dir / csv_name
                with z.open(csv_name) as f_in, open(out_path, 'wb') as f_out:
                    f_out.write(f_in.read())
            return out_path
        except Exception:
            # fallback to direct csv
            resp = requests.get(csv_url, timeout=60)
            if not resp.ok:
                raise RuntimeError(f"Failed to fetch gkgcounts for {date_str}")
            out_path = self.raw_counts_dir / f"{date_str}.gkgcounts.csv"
            out_path.write_bytes(resp.content)
            return out_path


if __name__ == '__main__':
    fetcher = GDELTFetcher()
    latest = fetcher.fetch_latest_15min()
    print(f"Saved latest 15-min GKG: {latest}")
    daily = fetcher.fetch_daily_counts()
    print(f"Saved daily gkgcounts: {daily}")
