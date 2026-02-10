import duckdb
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict


REPO_ROOT = Path(__file__).resolve().parents[1]


PROTEST_CODES = ['14', '140', '141', '142', '143', '144', '145']
VIOLENCE_CODES = ['18', '180', '181', '182', '183', '184', '185', '186',
                  '19', '190', '191', '192', '193', '194', '195', '196',
                  '20', '200', '201', '202', '203', '204']
COERCION_CODES = ['17', '170', '171', '172', '173', '174', '175']


class ConflictMonitor:
    def __init__(self, db_path: Optional[str] = None):
        default_path = REPO_ROOT / "data" / "gdelt_conflicts.duckdb"
        self.db_path = Path(db_path) if db_path is not None else default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = duckdb.connect(str(self.db_path))
        self._setup_database()

    def _setup_database(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS conflict_events (
                GlobalEventID BIGINT PRIMARY KEY,
                EventDate DATE,
                EventTimeAdded TIMESTAMP,
                EventRootCode VARCHAR,
                EventBaseCode VARCHAR,
                QuadClass INTEGER,
                GoldsteinScale DOUBLE,
                NumMentions INTEGER,
                NumSources INTEGER,
                AvgTone DOUBLE,
                Actor1CountryCode VARCHAR,
                Actor2CountryCode VARCHAR,
                Actor1Name VARCHAR,
                Actor2Name VARCHAR,
                ActionGeo_CountryCode VARCHAR,
                ActionGeo_FullName VARCHAR,
                ActionGeo_Lat DOUBLE,
                ActionGeo_Long DOUBLE,
                SourceURL VARCHAR,
                event_category VARCHAR,
                severity_score DOUBLE
            )
        """)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS casualty_counts (
                EventID BIGINT,
                count_type VARCHAR,
                count INTEGER,
                source_context VARCHAR,
                extracted_date TIMESTAMP,
                FOREIGN KEY (EventID) REFERENCES conflict_events(GlobalEventID)
            )
        """)

    def categorize_and_filter(self, events: List[Dict]) -> List[Dict]:
        filtered = []
        
        for event in events:
            props = event.get("properties", {})
            event_code = props.get("eventcode", "")
            event_root = event_code[:2] if len(event_code) >= 2 else ""
            
            if not event_root:
                continue
            
            is_conflict = (
                event_root in PROTEST_CODES + VIOLENCE_CODES + COERCION_CODES or
                props.get("category") in ["CONFLICT", "VIOLENCE", "PROTEST"]
            )
            
            if not is_conflict:
                continue
            
            event_category = 'other'
            if event_root.startswith('14'):
                event_category = 'protest'
            elif event_root in ['18', '19', '20']:
                event_category = 'violence'
            elif event_root == '17':
                event_category = 'coercion'
            
            num_sources = props.get("importance", 1) or 1
            num_mentions = props.get("importance", 1) or 1
            
            goldstein = -5.0
            if event_category == 'violence':
                goldstein = -8.0
            elif event_category == 'protest':
                goldstein = -3.0
            
            severity_score = (
                -goldstein * 2 +
                num_mentions * 0.5 +
                num_sources * 1.5
            )
            
            event_date_str = props.get("date", "")
            try:
                if len(event_date_str) >= 8:
                    event_date = datetime.strptime(event_date_str[:8], "%Y%m%d").date()
                else:
                    event_date = datetime.now(timezone.utc).date()
            except:
                event_date = datetime.now(timezone.utc).date()
            
            geo = event.get("geometry", {}).get("coordinates", [None, None])
            lat = geo[1] if len(geo) > 1 else None
            lng = geo[0] if len(geo) > 0 else None
            
            filtered_event = {
                "GlobalEventID": int(props.get("eventid", "0")) if props.get("eventid") else None,
                "EventDate": event_date,
                "EventTimeAdded": datetime.now(timezone.utc),
                "EventRootCode": event_root,
                "EventBaseCode": event_code,
                "QuadClass": 4 if event_category in ['violence', 'coercion'] else 3,
                "GoldsteinScale": goldstein,
                "NumMentions": num_mentions,
                "NumSources": num_sources,
                "AvgTone": -5.0,
                "Actor1CountryCode": props.get("actor1countrycode", ""),
                "Actor2CountryCode": props.get("actor2countrycode", ""),
                "Actor1Name": props.get("actor1", ""),
                "Actor2Name": props.get("actor2", ""),
                "ActionGeo_CountryCode": props.get("actiongeo_countrycode", ""),
                "ActionGeo_FullName": props.get("actiongeo") or props.get("countryname", ""),
                "ActionGeo_Lat": lat,
                "ActionGeo_Long": lng,
                "SourceURL": props.get("sourceurl", ""),
                "event_category": event_category,
                "severity_score": severity_score
            }
            
            if filtered_event["GlobalEventID"]:
                filtered.append(filtered_event)
        
        return filtered

    def detect_high_impact_events(self, conflict_events: List[Dict]) -> List[Dict]:
        if not conflict_events:
            return []
        
        severity_scores = [e.get("severity_score", 0) for e in conflict_events]
        if not severity_scores:
            return []
        
        threshold = sorted(severity_scores)[int(len(severity_scores) * 0.9)] if len(severity_scores) > 10 else severity_scores[0]
        
        high_impact = [
            e for e in conflict_events
            if (e.get("severity_score", 0) > threshold or
                e.get("NumSources", 0) > 20 or
                e.get("GoldsteinScale", 0) < -8 or
                e.get("EventRootCode") == '20')
        ]
        
        return sorted(high_impact, key=lambda x: x.get("severity_score", 0), reverse=True)

    def store_events(self, conflict_events: List[Dict]):
        if not conflict_events:
            return
        
        for event in conflict_events:
            try:
                self.db.execute("""
                    INSERT INTO conflict_events 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (GlobalEventID) DO UPDATE SET
                        EventTimeAdded = EXCLUDED.EventTimeAdded,
                        NumMentions = EXCLUDED.NumMentions,
                        NumSources = EXCLUDED.NumSources,
                        severity_score = EXCLUDED.severity_score
                """, [
                    event.get("GlobalEventID"),
                    event.get("EventDate"),
                    event.get("EventTimeAdded"),
                    event.get("EventRootCode"),
                    event.get("EventBaseCode"),
                    event.get("QuadClass"),
                    event.get("GoldsteinScale"),
                    event.get("NumMentions"),
                    event.get("NumSources"),
                    event.get("AvgTone"),
                    event.get("Actor1CountryCode"),
                    event.get("Actor2CountryCode"),
                    event.get("Actor1Name"),
                    event.get("Actor2Name"),
                    event.get("ActionGeo_CountryCode"),
                    event.get("ActionGeo_FullName"),
                    event.get("ActionGeo_Lat"),
                    event.get("ActionGeo_Long"),
                    event.get("SourceURL"),
                    event.get("event_category"),
                    event.get("severity_score")
                ])
            except Exception as e:
                print(f"[ConflictMonitor] Store error for {event.get('GlobalEventID')}: {e}")

    def generate_alerts(self, high_impact: List[Dict]) -> List[Dict]:
        alerts = []
        for event in high_impact:
            alert = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'event_id': event.get('GlobalEventID'),
                'category': event.get('event_category'),
                'severity': event.get('severity_score'),
                'location': event.get('ActionGeo_FullName'),
                'country': event.get('ActionGeo_CountryCode'),
                'description': f"{event.get('Actor1Name', 'Unknown')} {event.get('EventBaseCode', '')} {event.get('Actor2Name', '')}",
                'goldstein': event.get('GoldsteinScale'),
                'sources': event.get('NumSources'),
                'tone': event.get('AvgTone'),
                'url': event.get('SourceURL', '')
            }
            alerts.append(alert)
        return alerts

    def process_events(self, events: List[Dict]) -> Dict:
        conflict_events = self.categorize_and_filter(events)
        high_impact = self.detect_high_impact_events(conflict_events)
        self.store_events(conflict_events)
        alerts = self.generate_alerts(high_impact)
        
        return {
            'total_conflict_events': len(conflict_events),
            'high_impact_count': len(high_impact),
            'alerts': alerts
        }

    def query_protests(self, days: int = 7, min_sources: int = 10) -> List[Dict]:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
        result = self.db.execute("""
            SELECT 
                EventDate,
                ActionGeo_FullName as Location,
                Actor1Name,
                Actor2Name,
                NumSources,
                NumMentions,
                AvgTone,
                SourceURL,
                severity_score
            FROM conflict_events
            WHERE event_category = 'protest'
                AND EventDate >= ?
                AND NumSources > ?
            ORDER BY NumSources DESC, severity_score DESC
        """, [cutoff, min_sources]).fetchall()
        
        columns = ['EventDate', 'Location', 'Actor1Name', 'Actor2Name', 
                   'NumSources', 'NumMentions', 'AvgTone', 'SourceURL', 'severity_score']
        return [dict(zip(columns, row)) for row in result]

    def query_mass_casualty(self, days: int = 7) -> List[Dict]:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
        result = self.db.execute("""
            SELECT 
                ce.EventDate,
                ce.ActionGeo_FullName,
                ce.EventBaseCode,
                ce.GoldsteinScale,
                ce.NumSources,
                ce.severity_score
            FROM conflict_events ce
            WHERE ce.EventRootCode IN ('18', '19', '20')
                AND ce.EventDate >= ?
            ORDER BY ce.severity_score DESC, ce.NumSources DESC
        """, [cutoff]).fetchall()
        
        columns = ['EventDate', 'Location', 'EventCode', 'GoldsteinScale', 
                   'NumSources', 'severity_score']
        return [dict(zip(columns, row)) for row in result]

    def query_hotspots(self, days: int = 7) -> List[Dict]:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
        result = self.db.execute("""
            SELECT 
                ActionGeo_CountryCode,
                COUNT(*) as event_count,
                AVG(GoldsteinScale) as avg_severity,
                SUM(CASE WHEN event_category = 'violence' THEN 1 ELSE 0 END) as violence_count,
                SUM(CASE WHEN event_category = 'protest' THEN 1 ELSE 0 END) as protest_count
            FROM conflict_events
            WHERE EventDate >= ?
            GROUP BY ActionGeo_CountryCode
            HAVING event_count > 5
            ORDER BY violence_count DESC, event_count DESC
        """, [cutoff]).fetchall()
        
        columns = ['CountryCode', 'event_count', 'avg_severity', 
                   'violence_count', 'protest_count']
        return [dict(zip(columns, row)) for row in result]
