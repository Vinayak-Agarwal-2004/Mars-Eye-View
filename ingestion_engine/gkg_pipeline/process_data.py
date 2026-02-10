from pathlib import Path
import pandas as pd
import duckdb
import yaml


class DataProcessor:
    def __init__(self, config_path: str = None):
        config_path = config_path or Path(__file__).with_name('config.yaml')
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.db_path = self.config['paths']['db_path']
        self.processed_dir = Path(self.config['paths']['processed_dir'])
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.conn = duckdb.connect(self.db_path)
        self.setup_tables()

    def setup_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gdelt_metrics (
                date DATE,
                country VARCHAR,
                metric_type VARCHAR,
                count BIGINT,
                num_sources BIGINT,
                source VARCHAR,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gdelt_admin1_metrics (
                date DATE,
                country VARCHAR,
                admin1 VARCHAR,
                metric_type VARCHAR,
                count BIGINT,
                num_sources BIGINT,
                source VARCHAR,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def process_gdelt_counts(self, csv_path: str | Path):
        cols = ['date', 'num_sources', 'count_type', 'number', 'object_type',
                'geo_type', 'country', 'adm1', 'lat', 'lon', 'geo_id', 'urls']

        df = pd.read_csv(
            csv_path,
            sep='\t',
            header=None,
            names=cols,
            usecols=list(range(12)),
            low_memory=False
        )

        df = df[df['count_type'].isin(self.config['metrics'])]
        if df.empty:
            return None

        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
        df = df.dropna(subset=['date'])

        agg_country = df.groupby(['date', 'country', 'count_type']).agg({
            'number': 'sum',
            'num_sources': 'sum'
        }).reset_index()
        agg_country.columns = ['date', 'country', 'metric_type', 'count', 'num_sources']
        agg_country['source'] = 'GDELT'

        agg_admin1 = df.groupby(['date', 'country', 'adm1', 'count_type']).agg({
            'number': 'sum',
            'num_sources': 'sum'
        }).reset_index()
        agg_admin1.columns = ['date', 'country', 'admin1', 'metric_type', 'count', 'num_sources']
        agg_admin1['source'] = 'GDELT'

        # Insert into DuckDB
        self.conn.register('agg_country', agg_country)
        self.conn.execute(
            """
            INSERT INTO gdelt_metrics (date, country, metric_type, count, num_sources, source)
            SELECT date, country, metric_type, count, num_sources, source FROM agg_country
            """
        )

        self.conn.register('agg_admin1', agg_admin1)
        self.conn.execute(
            """
            INSERT INTO gdelt_admin1_metrics (date, country, admin1, metric_type, count, num_sources, source)
            SELECT date, country, admin1, metric_type, count, num_sources, source FROM agg_admin1
            """
        )

        # Emit daily processed files for convenience
        day_str = agg_country['date'].iloc[0].strftime('%Y%m%d')
        agg_country.to_csv(self.processed_dir / f"gdelt_metrics_{day_str}.csv", index=False)
        agg_admin1.to_csv(self.processed_dir / f"gdelt_admin1_metrics_{day_str}.csv", index=False)

        return {
            'country_rows': len(agg_country),
            'admin1_rows': len(agg_admin1),
            'date': day_str
        }

    def get_daily_summary(self, days: int = 30):
        query = f"""
            SELECT
                date,
                country,
                SUM(CASE WHEN metric_type IN ('KILL', 'CRISISLEXT03DEAD') THEN count ELSE 0 END) AS deaths,
                SUM(CASE WHEN metric_type IN ('INJURED', 'CRISISLEXT02INJURED') THEN count ELSE 0 END) AS injured,
                SUM(CASE WHEN metric_type IN ('DISPLACED', 'REFUGEES') THEN count ELSE 0 END) AS displaced,
                SUM(CASE WHEN metric_type = 'PROTEST' THEN count ELSE 0 END) AS protests
            FROM gdelt_metrics
            WHERE date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY date, country
            ORDER BY date DESC, country
        """
        return self.conn.execute(query).df()


if __name__ == '__main__':
    processor = DataProcessor()
    raw_dir = Path(processor.config['paths']['raw_gkgcounts_dir'])
    for csv_file in sorted(raw_dir.glob('*.gkgcounts.csv')):
        result = processor.process_gdelt_counts(csv_file)
        if result:
            print(f"Processed {csv_file}: {result}")
