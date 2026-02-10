import requests
import zipfile
import io
import csv
import os
import json
import time
import threading
from datetime import datetime, timedelta, timezone
from ..core.taxonomy import GDELT_MAPPING, THEME_MAPPING, COLORS
from .checkpoint import CheckpointManager
from .alerting import AlertingService

class FirehoseService:
    def __init__(self):
        self.latest_data = {"type": "FeatureCollection", "features": []}
        self.last_update = None
        self.running = False
        self.seen_urls = set()
        self.output_file = "data/live/gdelt_latest.json"
        self.history_file = "data/live/gdelt_window.json"
        self.history_window_hours = int(os.getenv("GDELT_HISTORY_HOURS", "720"))
        self.history_index = {}
        self.history_data = {"type": "FeatureCollection", "features": []}
        
        self.checkpoint_manager = CheckpointManager()
        self.alerting_service = AlertingService()
        
        # Load initial state from disk
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r') as f:
                    self.latest_data = json.load(f)
            except: pass

        # Load rolling window history if available
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    history_blob = json.load(f)
                features = history_blob.get("features", [])
                for feat in features:
                    sig = self._signature(feat)
                    if sig:
                        self.history_index[sig] = feat
                self.history_data = {"type": "FeatureCollection", "features": list(self.history_index.values())}
                print(f"[Firehose] Loaded history window: {len(self.history_index)} events")
            except Exception as e:
                print(f"[Firehose] History load failed: {e}")

    def start(self):
        if self.running: return
        self.running = True
        # Startup procedure: fetch immediately to ensure data is ready.
        try:
            self._fetch_cycle()
        except Exception as e:
            print(f"[Firehose] Startup fetch failed: {e}")
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        print("[Firehose] Service Started")

    def get_history(self, hours: int = 168, transnational: bool = False):
        """
        Return historical events within the specified time window.
        transnational: If True, filter for international events only.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        filtered = []
        for feat in self.history_data.get("features", []):
            props = feat.get("properties", {})
            ingested_at = props.get("ingested_at")
            
            # 1. Time Filtering
            keep_time = False
            # Parse ingested_at timestamp
            if ingested_at:
                try:
                    ts = datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
                    if ts >= cutoff: keep_time = True
                except (ValueError, TypeError):
                    keep_time = True # Fallback
            else:
                # Fallback: use date field if available
                date_str = props.get("date", "")
                if date_str:
                    try:
                        ts = datetime.strptime(date_str[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
                        if ts >= cutoff: keep_time = True
                    except (ValueError, TypeError):
                        keep_time = True
                else:
                    keep_time = True
            
            if not keep_time:
                continue

            # 2. Transnational Filtering
            if transnational:
                a1 = props.get("actor1countrycode")
                a2 = props.get("actor2countrycode")
                # Logic: Must have 2 distinct actors from different countries
                if not a1 or not a2 or a1 == a2:
                    continue
            
            filtered.append(feat)
        
        return {"type": "FeatureCollection", "features": filtered}


    def _loop(self):
        while self.running:
            try:
                self._fetch_cycle()
            except Exception as e:
                print(f"[Firehose] Error: {e}")
            time.sleep(60 * 15) # 15 min cycle

    def _fetch_cycle(self):
        print(f"[{datetime.now()}] Checking GDELT...")
        # 1. Get List
        resp = requests.get("http://data.gdeltproject.org/gdeltv2/lastupdate.txt", timeout=30)
        lines = resp.text.splitlines()

        export_url = None
        mentions_url = None
        for line in lines:
            parts = line.strip().split(' ')
            if len(parts) < 3:
                continue
            url = parts[2]
            url_lower = url.lower()
            if "mentions" in url_lower and url_lower.endswith(".csv.zip"):
                mentions_url = url
            elif "export" in url_lower and url_lower.endswith(".csv.zip"):
                export_url = url

        # Fallback derivation if mentions not found but export is known
        if export_url and not mentions_url:
            mentions_url = export_url.replace(".export.", ".mentions.").replace("export.csv.zip", "mentions.csv.zip")

        if not export_url or not mentions_url:
            print("  > GDELT lastupdate parse failed (missing export or mentions URL).")
            return
        
        if export_url in self.seen_urls:
            print("  > No new update.")
            return

        print(f"  > Downloading Export & Mentions...")
        self.seen_urls.add(export_url)
        
        # 2. Extract Mentions First (to build URL map)
        mention_map = {} # GlobalEventID -> set(URLs)
        try:
            r_m = requests.get(mentions_url, timeout=30)
            z_m = zipfile.ZipFile(io.BytesIO(r_m.content))
            with z_m.open(z_m.namelist()[0]) as f:
                content = io.TextIOWrapper(f)
                reader = csv.reader(content, delimiter='\t')
                for row in reader:
                    if len(row) < 6: continue
                    eid = row[0]
                    url = row[5]
                    if not url:
                        continue
                    if not url.startswith("http"):
                        continue
                    if eid not in mention_map:
                        mention_map[eid] = set()
                    mention_map[eid].add(url)
        except Exception as e:
            print(f"  > Mentions Error: {e}")

        # 3. Extract & Parse Export
        r_e = requests.get(export_url)
        z_e = zipfile.ZipFile(io.BytesIO(r_e.content))
        
        features = []
        ingest_time = datetime.now(timezone.utc)
        with z_e.open(z_e.namelist()[0]) as f:
            content = io.TextIOWrapper(f)
            reader = csv.reader(content, delimiter='\t')
            for row in reader:
                eid = row[0]
                feat = self._parse_row(row)
                if feat:
                    # Append all links from mentions
                    extra_links = mention_map.get(eid, set())
                    # Seed with the primary link if not present
                    primary_link = feat["properties"].get("sourceurl")
                    all_urls = set(extra_links)
                    if primary_link: all_urls.add(primary_link)
                    
                    feat["properties"]["sources"] = [
                        {"url": u, "type": "article", "name": "GDELT Source"} 
                        for u in sorted(list(all_urls))
                    ]
                    feat["properties"]["ingested_at"] = ingest_time.isoformat()
                    feat["properties"]["eventid"] = eid
                    feat["properties"]["event_sig"] = self._signature(feat)
                    features.append(feat)
        
        # 4. Update State
        self.latest_data = {
            "type": "FeatureCollection", 
            "features": features
        }
        self.last_update = datetime.now(timezone.utc)

        # 4b. Update rolling window
        self._update_history(features, ingest_time)
        
        # 4c. Process conflict events and send alerts
        self._process_conflicts(features)
        
        # 4d. Process diplomatic relations
        self._process_diplomacy(features)

        if os.getenv("GDELT_INTERACTIONS_ON_FIREHOSE", "").lower() in ("1", "true", "yes"):
            self._trigger_interactions_update()

        # 5. Persist
        with open(self.output_file, 'w') as f:
            json.dump(self.latest_data, f)

        with open(self.history_file, 'w') as f:
            json.dump(self.history_data, f)
        
        # Save checkpoint
        self.checkpoint_manager.save_checkpoint(
            timestamp=ingest_time,
            processed_count=len(features),
            metadata={
                'export_url': export_url,
                'mentions_url': mentions_url,
                'features_count': len(features)
            }
        )
            
        print(f"  > Updated {len(features)} events with multi-link support.")

    def _parse_row(self, row):
        try:
            if len(row) < 58:
                return None
            def pick_value(indices):
                for idx in indices:
                    if idx < 0:
                        if len(row) == 0:
                            continue
                        val = row[idx]
                        if val:
                            return val
                        continue
                    if len(row) > idx and row[idx]:
                        return row[idx]
                return ''

            lat = pick_value([56, 53, 39])
            lng = pick_value([57, 54, 40])
            if not lat or not lng: return None

            try:
                lat_val = float(lat)
                lng_val = float(lng)
            except Exception:
                return None
            if abs(lat_val) > 90 or abs(lng_val) > 180:
                return None
            
            code = row[26] if len(row) > 26 else '' # EventCode
            actor1 = row[6] if len(row) > 6 else ''
            actor2 = row[16] if len(row) > 16 else ''
            action_geo = row[52] if len(row) > 52 else ''
            action_adm1 = row[53] if len(row) > 53 else ''
            
            # Taxonomy
            # Taxonomy
            category = GDELT_MAPPING.get(code, "OTHER")
            if category == "OTHER": return None # Strict Filter
            
            # Reliability: 32: NumSources, 33: NumArticles (GDELT v2)
            try:
                num_sources = int(float(row[32])) if row[32] else 0
                num_articles = int(float(row[33])) if row[33] else 0
            except:
                num_sources = 0
                num_articles = 0
                
            if num_sources < 1: return None # Drop zero source events
            
            # Country
            country_name = action_geo or (row[52] if len(row) > 52 else '')
            source_url = ''
            source_url = pick_value([60, -1])
            
            # Transnational Fields
            a1_code = row[7] if len(row) > 7 else ''
            a2_code = row[17] if len(row) > 17 else ''
            geo_code = row[51] if len(row) > 51 else ''

            return {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng_val, lat_val]},
                "properties": {
                    "category": category,
                    "date": row[1],
                    "countryname": country_name,
                    "name": f"{category}: {row[6] or 'Unidentified'}",
                    "color": COLORS.get(category, '#808080'),
                    "importance": num_articles or 1,
                    "sourceurl": source_url,
                    "sources": [{"url": source_url, "type": "article", "name": "GDELT"}] if source_url else [],
                    "eventcode": code,
                    "actor1": actor1,
                    "actor2": actor2,
                    "actiongeo": action_geo,
                    "actionadm1": action_adm1,
                    "actor1countrycode": a1_code,
                    "actor2countrycode": a2_code,
                    "actiongeo_countrycode": geo_code
                }
            }
        except: return None

    def _signature(self, feature):
        props = feature.get("properties", {})
        event_id = props.get("eventid")
        if event_id:
            return f"eid:{event_id}"
        source = props.get("sourceurl")
        if source:
            return f"url:{source}"
        coords = feature.get("geometry", {}).get("coordinates", [None, None])
        name = props.get("name") or "unknown"
        date = props.get("date") or ""
        return f"sig:{name}|{date}|{coords[0]}|{coords[1]}"

    def _parse_ingested_at(self, feat):
        props = feat.get("properties", {})
        ts = props.get("ingested_at")
        if ts:
            try:
                # Handle both old format (+00:00Z) and new format (+00:00)
                ts_clean = ts.rstrip("Z")
                if not ts_clean.endswith("+00:00") and not ts_clean.endswith("-00:00"):
                    ts_clean = ts_clean + "+00:00"
                return datetime.fromisoformat(ts_clean)
            except Exception:
                return None
        date_str = props.get("date")
        if not date_str:
            return None
        try:
            if len(date_str) >= 14:
                return datetime.strptime(date_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            return datetime.strptime(date_str[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _update_history(self, features, ingest_time):
        # Insert or refresh by signature
        for feat in features:
            sig = feat.get("properties", {}).get("event_sig") or self._signature(feat)
            if not sig:
                continue
            self.history_index[sig] = feat

        # Prune older than window
        cutoff = ingest_time - timedelta(hours=self.history_window_hours)
        for sig, feat in list(self.history_index.items()):
            ts = self._parse_ingested_at(feat)
            if ts and ts < cutoff:
                del self.history_index[sig]

        self.history_data = {
            "type": "FeatureCollection",
            "features": list(self.history_index.values())
        }

    def _process_conflicts(self, features):
        try:
            from ingestion_engine.conflict_monitor import ConflictMonitor
            
            monitor = ConflictMonitor()
            result = monitor.process_events(features)
            
            if result.get('alerts'):
                self.alerting_service.send_alert(result['alerts'], source="conflict_monitor")
        except ImportError as e:
            print(f"[Firehose] Conflict monitor import failed: {e}")
        except Exception as e:
            print(f"[Firehose] Conflict processing failed: {e}")

    def _process_diplomacy(self, features):
        try:
            from ingestion_engine.diplomatic_tracker import DiplomaticRelationsTracker
            
            tracker = DiplomaticRelationsTracker()
            result = tracker.process_events(features)
            
            if result.get('top_escalation'):
                escalation_alerts = [
                    {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'category': 'escalation',
                        'severity': e.get('risk_score', 0),
                        'location': e.get('country_pair', 'Unknown'),
                        'description': f"Escalation risk: {e.get('risk_score', 0)}",
                        'url': ''
                    }
                    for e in result['top_escalation'][:5]
                ]
                self.alerting_service.send_alert(escalation_alerts, source="diplomatic_tracker")
        except ImportError as e:
            print(f"[Firehose] Diplomatic tracker import failed: {e}")
        except Exception as e:
            print(f"[Firehose] Diplomatic processing failed: {e}")

    def _trigger_interactions_update(self):
        try:
            from ingestion_engine.services.manifest_auto_updater import run_update_gdelt
            result = run_update_gdelt()
            if result.get("submitted"):
                print(f"[Firehose] Interactions update: {result.get('submitted')} events submitted")
        except Exception as e:
            print(f"[Firehose] Interactions update failed: {e}")
