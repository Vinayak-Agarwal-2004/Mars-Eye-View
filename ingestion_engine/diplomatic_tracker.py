import duckdb
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]


class DiplomaticRelationsTracker:
    def __init__(self, db_path: Optional[str] = None):
        default_path = REPO_ROOT / "data" / "gdelt_diplomacy.duckdb"
        self.db_path = Path(db_path) if db_path is not None else default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = duckdb.connect(str(self.db_path))
        self._setup_database()

    def _setup_database(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS country_interactions (
                GlobalEventID BIGINT PRIMARY KEY,
                EventDate DATE,
                Source_Country VARCHAR,
                Target_Country VARCHAR,
                EventRootCode VARCHAR,
                EventBaseCode VARCHAR,
                QuadClass INTEGER,
                GoldsteinScale DOUBLE,
                interaction_type VARCHAR,
                cooperation_score DOUBLE,
                NumSources INTEGER,
                AvgTone DOUBLE,
                SourceURL VARCHAR,
                extracted_timestamp TIMESTAMP
            )
        """)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS bilateral_relations (
                country_pair VARCHAR PRIMARY KEY,
                period_start DATE,
                period_end DATE,
                total_interactions INTEGER,
                cooperation_events INTEGER,
                conflict_events INTEGER,
                avg_goldstein DOUBLE,
                avg_tone DOUBLE,
                diplomatic_events INTEGER,
                military_events INTEGER,
                economic_events INTEGER,
                relation_trend VARCHAR,
                updated_at TIMESTAMP
            )
        """)

    def filter_bilateral_events(self, events: List[Dict]) -> List[Dict]:
        bilateral = []
        
        for event in events:
            props = event.get("properties", {})
            a1_code = props.get("actor1countrycode", "")
            a2_code = props.get("actor2countrycode", "")
            
            if (a1_code and a2_code and 
                a1_code != "" and a2_code != "" and 
                a1_code != a2_code):
                bilateral.append(event)
        
        return bilateral

    def categorize_interactions(self, events: List[Dict]) -> List[Dict]:
        categorized = []
        
        diplomatic_codes = ['01', '02', '03', '04', '05', '06', '07', '08', '09']
        military_codes = ['15', '16', '17', '18', '19', '20']
        economic_codes = ['061', '07']
        conflict_codes = ['18', '19', '20']
        
        for event in events:
            props = event.get("properties", {})
            event_code = props.get("eventcode", "")
            event_root = event_code[:2] if len(event_code) >= 2 else ""
            event_base = event_code[:3] if len(event_code) >= 3 else ""
            
            interaction_type = 'other'
            if event_root in conflict_codes:
                interaction_type = 'conflict'
            elif event_root in diplomatic_codes:
                interaction_type = 'diplomatic'
            elif event_base in economic_codes or event_root == '07':
                interaction_type = 'economic'
            elif event_root in military_codes:
                interaction_type = 'military'
            
            a1_code = props.get("actor1countrycode", "")
            a2_code = props.get("actor2countrycode", "")
            country_pair = '-'.join(sorted([a1_code, a2_code]))
            
            event_date_str = props.get("date", "")
            try:
                if len(event_date_str) >= 8:
                    event_date = datetime.strptime(event_date_str[:8], "%Y%m%d").date()
                else:
                    event_date = datetime.now(timezone.utc).date()
            except:
                event_date = datetime.now(timezone.utc).date()
            
            goldstein = -5.0
            if interaction_type == 'conflict':
                goldstein = -8.0
            elif interaction_type == 'diplomatic':
                goldstein = 3.0
            elif interaction_type == 'economic':
                goldstein = 2.0
            
            cooperation_score = goldstein
            
            num_sources = props.get("importance", 1) or 1
            
            categorized_event = {
                "GlobalEventID": int(props.get("eventid", "0")) if props.get("eventid") else None,
                "EventDate": event_date,
                "Source_Country": a1_code,
                "Target_Country": a2_code,
                "EventRootCode": event_root,
                "EventBaseCode": event_code,
                "QuadClass": 4 if interaction_type == 'conflict' else (1 if goldstein > 0 else 3),
                "GoldsteinScale": goldstein,
                "interaction_type": interaction_type,
                "cooperation_score": cooperation_score,
                "NumSources": num_sources,
                "AvgTone": -5.0 if interaction_type == 'conflict' else 0.0,
                "SourceURL": props.get("sourceurl", ""),
                "extracted_timestamp": datetime.now(timezone.utc),
                "country_pair": country_pair
            }
            
            if categorized_event["GlobalEventID"]:
                categorized.append(categorized_event)
        
        return categorized

    def compute_relation_metrics(self, interactions: List[Dict]) -> List[Dict]:
        if not interactions:
            return []
        
        pair_metrics = {}
        
        for event in interactions:
            pair = event.get("country_pair")
            if not pair:
                continue
            
            if pair not in pair_metrics:
                pair_metrics[pair] = {
                    "country_pair": pair,
                    "total_interactions": 0,
                    "cooperation_events": 0,
                    "conflict_events": 0,
                    "goldstein_sum": 0.0,
                    "tone_sum": 0.0,
                    "diplomatic_events": 0,
                    "military_events": 0,
                    "economic_events": 0,
                    "dates": []
                }
            
            metrics = pair_metrics[pair]
            metrics["total_interactions"] += 1
            metrics["goldstein_sum"] += event.get("GoldsteinScale", 0)
            metrics["tone_sum"] += event.get("AvgTone", 0)
            metrics["dates"].append(event.get("EventDate"))
            
            quad_class = event.get("QuadClass", 0)
            if quad_class <= 2:
                metrics["cooperation_events"] += 1
            elif quad_class >= 3:
                metrics["conflict_events"] += 1
            
            interaction_type = event.get("interaction_type", "")
            if interaction_type == 'diplomatic':
                metrics["diplomatic_events"] += 1
            elif interaction_type == 'military':
                metrics["military_events"] += 1
            elif interaction_type == 'economic':
                metrics["economic_events"] += 1
        
        results = []
        for pair, metrics in pair_metrics.items():
            total = metrics["total_interactions"]
            if total == 0:
                continue
            
            avg_goldstein = metrics["goldstein_sum"] / total
            avg_tone = metrics["tone_sum"] / total
            
            relation_trend = 'stable'
            if avg_goldstein > 2:
                relation_trend = 'improving'
            elif avg_goldstein < -2:
                relation_trend = 'deteriorating'
            
            dates = [d for d in metrics["dates"] if d]
            period_start = min(dates) if dates else datetime.now(timezone.utc).date()
            period_end = max(dates) if dates else datetime.now(timezone.utc).date()
            
            results.append({
                "country_pair": pair,
                "period_start": period_start,
                "period_end": period_end,
                "total_interactions": metrics["total_interactions"],
                "cooperation_events": metrics["cooperation_events"],
                "conflict_events": metrics["conflict_events"],
                "avg_goldstein": avg_goldstein,
                "avg_tone": avg_tone,
                "diplomatic_events": metrics["diplomatic_events"],
                "military_events": metrics["military_events"],
                "economic_events": metrics["economic_events"],
                "relation_trend": relation_trend,
                "updated_at": datetime.now(timezone.utc)
            })
        
        return results

    def detect_significant_developments(self, interactions: List[Dict]) -> List[Dict]:
        significant = []
        
        for event in interactions:
            num_sources = event.get("NumSources", 0)
            goldstein = abs(event.get("GoldsteinScale", 0))
            event_root = event.get("EventRootCode", "")
            
            if (num_sources > 15 or
                goldstein > 7 or
                event_root in ['19', '20']):
                
                priority_score = (
                    num_sources * 2 +
                    goldstein * 5 +
                    (50 if event_root in ['19', '20'] else 0)
                )
                
                event["priority_score"] = priority_score
                significant.append(event)
        
        return sorted(significant, key=lambda x: x.get("priority_score", 0), reverse=True)

    def track_war_indicators(self, interactions: List[Dict]) -> List[Dict]:
        war_codes = ['13', '15', '17', '18', '19', '20']
        war_events = [e for e in interactions if e.get("EventRootCode") in war_codes]
        
        pair_escalation = {}
        
        for event in war_events:
            pair = event.get("country_pair")
            if not pair:
                continue
            
            if pair not in pair_escalation:
                pair_escalation[pair] = {
                    "country_pair": pair,
                    "threat_score": 0,
                    "military_posture": 0,
                    "active_conflict": 0
                }
            
            escalation = pair_escalation[pair]
            event_root = event.get("EventRootCode", "")
            
            if event_root == '13':
                escalation["threat_score"] += 2
            elif event_root == '15':
                escalation["military_posture"] += 3
            elif event_root in ['18', '19', '20']:
                escalation["active_conflict"] += 10
        
        results = []
        for pair, escalation in pair_escalation.items():
            risk_score = (
                escalation["threat_score"] +
                escalation["military_posture"] +
                escalation["active_conflict"]
            )
            
            if risk_score > 0:
                escalation["risk_score"] = risk_score
                results.append(escalation)
        
        return sorted(results, key=lambda x: x.get("risk_score", 0), reverse=True)

    def store_interactions(self, interactions: List[Dict]):
        if not interactions:
            return
        
        for event in interactions:
            try:
                self.db.execute("""
                    INSERT INTO country_interactions 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (GlobalEventID) DO UPDATE SET
                        extracted_timestamp = EXCLUDED.extracted_timestamp,
                        NumSources = EXCLUDED.NumSources
                """, [
                    event.get("GlobalEventID"),
                    event.get("EventDate"),
                    event.get("Source_Country"),
                    event.get("Target_Country"),
                    event.get("EventRootCode"),
                    event.get("EventBaseCode"),
                    event.get("QuadClass"),
                    event.get("GoldsteinScale"),
                    event.get("interaction_type"),
                    event.get("cooperation_score"),
                    event.get("NumSources"),
                    event.get("AvgTone"),
                    event.get("SourceURL"),
                    event.get("extracted_timestamp")
                ])
            except Exception as e:
                print(f"[DiplomaticTracker] Store error for {event.get('GlobalEventID')}: {e}")

    def store_bilateral_relations(self, relations: List[Dict]):
        if not relations:
            return
        
        for relation in relations:
            try:
                self.db.execute("""
                    INSERT INTO bilateral_relations 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (country_pair) DO UPDATE SET
                        period_end = EXCLUDED.period_end,
                        total_interactions = EXCLUDED.total_interactions,
                        cooperation_events = EXCLUDED.cooperation_events,
                        conflict_events = EXCLUDED.conflict_events,
                        avg_goldstein = EXCLUDED.avg_goldstein,
                        avg_tone = EXCLUDED.avg_tone,
                        diplomatic_events = EXCLUDED.diplomatic_events,
                        military_events = EXCLUDED.military_events,
                        economic_events = EXCLUDED.economic_events,
                        relation_trend = EXCLUDED.relation_trend,
                        updated_at = EXCLUDED.updated_at
                """, [
                    relation.get("country_pair"),
                    relation.get("period_start"),
                    relation.get("period_end"),
                    relation.get("total_interactions"),
                    relation.get("cooperation_events"),
                    relation.get("conflict_events"),
                    relation.get("avg_goldstein"),
                    relation.get("avg_tone"),
                    relation.get("diplomatic_events"),
                    relation.get("military_events"),
                    relation.get("economic_events"),
                    relation.get("relation_trend"),
                    relation.get("updated_at")
                ])
            except Exception as e:
                print(f"[DiplomaticTracker] Store relation error for {relation.get('country_pair')}: {e}")

    def process_events(self, events: List[Dict]) -> Dict:
        bilateral = self.filter_bilateral_events(events)
        categorized = self.categorize_interactions(bilateral)
        self.store_interactions(categorized)
        
        relations = self.compute_relation_metrics(categorized)
        self.store_bilateral_relations(relations)
        
        significant = self.detect_significant_developments(categorized)
        escalation = self.track_war_indicators(categorized)
        
        return {
            'total_bilateral': len(bilateral),
            'categorized': len(categorized),
            'relations_count': len(relations),
            'significant_developments': len(significant),
            'escalation_risks': len(escalation),
            'top_relations': relations[:10],
            'top_escalation': escalation[:5],
            'top_significant': significant[:10]
        }

    def query_network_centrality(self, days: int = 30) -> List[Dict]:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
        result = self.db.execute("""
            SELECT 
                country,
                COUNT(DISTINCT partner_country) as num_partners,
                SUM(interactions) as total_interactions,
                AVG(avg_goldstein) as avg_relation_quality
            FROM (
                SELECT Source_Country as country, Target_Country as partner_country,
                       COUNT(*) as interactions, AVG(GoldsteinScale) as avg_goldstein
                FROM country_interactions
                WHERE EventDate >= ?
                GROUP BY Source_Country, Target_Country
                
                UNION ALL
                
                SELECT Target_Country as country, Source_Country as partner_country,
                       COUNT(*) as interactions, AVG(GoldsteinScale) as avg_goldstein
                FROM country_interactions
                WHERE EventDate >= ?
                GROUP BY Target_Country, Source_Country
            ) subquery
            GROUP BY country
            ORDER BY total_interactions DESC
            LIMIT 20
        """, [cutoff, cutoff]).fetchall()
        
        columns = ['country', 'num_partners', 'total_interactions', 'avg_relation_quality']
        return [dict(zip(columns, row)) for row in result]

    def query_conflict_pairs(self, days: int = 30) -> List[Dict]:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
        result = self.db.execute("""
            SELECT 
                CASE 
                    WHEN Source_Country < Target_Country 
                    THEN Source_Country || '-' || Target_Country
                    ELSE Target_Country || '-' || Source_Country
                END as country_pair,
                COUNT(*) as conflict_events,
                AVG(GoldsteinScale) as avg_severity,
                MIN(EventDate) as first_incident,
                MAX(EventDate) as latest_incident
            FROM country_interactions
            WHERE QuadClass = 4
                AND EventDate >= ?
            GROUP BY country_pair
            HAVING COUNT(*) >= 3
            ORDER BY conflict_events DESC, avg_severity ASC
        """, [cutoff]).fetchall()
        
        columns = ['country_pair', 'conflict_events', 'avg_severity', 
                   'first_incident', 'latest_incident']
        return [dict(zip(columns, row)) for row in result]
