from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from math import floor
from pathlib import Path
import json

from sklearn.cluster import DBSCAN
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
ANOMALY_BASELINE_FILE = REPO_ROOT / "data" / "live" / "gdelt_anomaly_baseline.json"

class HotspotAnalyzer:
    def __init__(self, firehose):
        self.firehose = firehose

    def analyze(self, window_hours: int = 48, previous_hours: int | None = None,
                grid_km: int = 120, top: int = 10, clustering_method: str = "grid", 
                dbscan_eps: float = 50.0, dbscan_min_samples: int = 5,
                transnational: bool = False):
        now = datetime.now(timezone.utc)
        prev_hours = previous_hours or window_hours
        current_start = now - timedelta(hours=window_hours)
        previous_start = now - timedelta(hours=window_hours + prev_hours)
        previous_end = current_start

        # Enforce Transnational for DBSCAN (per user request)
        if clustering_method == "dbscan":
            transnational = True

        features = (self.firehose.history_data or {}).get("features", [])
        
        if transnational:
            features = [f for f in features if self._is_transnational(f)]

        current = []
        previous = []
        for feat in features:
            ts = self._get_ingested_at(feat)
            if ts is None:
                continue
            if ts >= current_start:
                current.append(feat)
            elif previous_start <= ts < previous_end:
                previous.append(feat)

        if clustering_method == "dbscan":
            current_stats = self._build_dbscan_stats(current, dbscan_eps, dbscan_min_samples)
            previous_stats = self._build_dbscan_stats(previous, dbscan_eps, dbscan_min_samples)
        else:
            current_stats = self._build_stats(current, grid_km)
            previous_stats = self._build_stats(previous, grid_km)

        hotspots = {
            "location": self._score_and_rank(current_stats["location"], previous_stats["location"], top),
            "event": self._score_and_rank(current_stats["event"], previous_stats["event"], top),
            "actor": self._score_and_rank(current_stats["actor"], previous_stats["actor"], top),
        }

        return {
            "generated_at": now.isoformat(),
            "window_hours": window_hours,
            "previous_hours": prev_hours,
            "grid_km": grid_km,
            "counts": {
                "current_events": len(current),
                "previous_events": len(previous),
            },
            "hotspots": hotspots,
            "methodology": {
                "scoring": "score = weighted_count * (1 + trend), trend = (current - previous) / max(1, previous)",
                "location_cluster": "grid cell by grid_km; aggregated counts and categories",
                "event_cluster": "eventcode + category + actiongeo (fallback to name)",
                "actor_cluster": "actor1/actor2 names normalized",
            }
        }

    def _is_transnational(self, feat):
        p = feat.get("properties", {})
        a1 = p.get("actor1countrycode")
        a2 = p.get("actor2countrycode")
        # Logic: Must have 2 distinct actors from different countries
        if a1 and a2 and a1 != a2:
            return True
        
        # Logic: Actor acting in different country
        # DISABLED: Mismatch between CAMEO (ISO-3 like 'USA') and FIPS ('US') causes false positives.
        # geo = p.get("actiongeo_countrycode")
        # if a1 and geo and a1 != geo:
        #    return True
            
        return False

    def _get_ingested_at(self, feature):
        props = feature.get("properties", {})
        ts = props.get("ingested_at")
        if ts:
            try:
                # Handle both old format (+00:00Z) and new format (+00:00)
                ts_clean = ts.rstrip("Z")  # Remove trailing Z if present
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

    def _normalize_actor(self, value: str):
        if not value:
            return None
        cleaned = ''.join(ch.lower() if ch.isalnum() or ch.isspace() else ' ' for ch in value)
        cleaned = ' '.join(cleaned.split())
        if len(cleaned) < 3:
            return None
        return cleaned

    def _grid_key(self, lat: float, lng: float, grid_km: int):
        cell_deg = grid_km / 111.0
        gx = floor(lat / cell_deg)
        gy = floor(lng / cell_deg)
        return f"{gx}:{gy}", (gx + 0.5) * cell_deg, (gy + 0.5) * cell_deg

    def _build_dbscan_stats(self, features, eps_km: float = 50.0, min_samples: int = 5):
        """
        Cluster events using DBSCAN for density-based hotspots.
        eps_km: max distance between points in same cluster
        min_samples: min points to form a cluster
        """
        location_stats = defaultdict(self._empty_stat)
        event_stats = defaultdict(self._empty_stat)
        actor_stats = defaultdict(self._empty_stat)

        # Extract coordinates [lat, lng]
        coords = []
        valid_features = []
        for feat in features:
            geo = feat.get("geometry", {}).get("coordinates", [])
            if len(geo) >= 2:
                coords.append([geo[1], geo[0]])  # lat, lng
                valid_features.append(feat)

        if not coords:
            return {
                "location": location_stats,
                "event": event_stats,
                "actor": actor_stats,
            }

        # Convert to radians for Haversine metric
        # Earth radius approx 6371 km
        eps_radians = eps_km / 6371.0
        X = np.radians(coords)

        # Run DBSCAN
        # metric='haversine' expects [lat, long] in radians
        db = DBSCAN(eps=eps_radians, min_samples=min_samples, metric='haversine').fit(X)
        
        labels = db.labels_
        
        # Aggregate stats by cluster
        for i, label in enumerate(labels):
            feat = valid_features[i]
            props = feat.get("properties", {})
            
            # Label -1 is noise
            if label == -1:
                # Treat noise as individual points? or ignore?
                # For hotspots, we usually ignore noise or treat as separate tiny clusters
                # Let's ignore noise for location hotspots to focus on density
                pass
            else:
                cluster_key = f"cluster_{label}"
                stat = location_stats[cluster_key]
                stat["count"] += 1
                stat["weighted_count"] += 1.0  # could use GoldsteinScale here
                
                self._accumulate_metadata(stat, props, coords[i])

            # Event and Actor stats are global or per-grid in original?
            # In original _build_stats, event/actor stats were independent of grid
            # Wait, no. The original _build_stats aggregated event/actor stats globally?
            # Let's check _build_stats implementation.
            # It aggregates location_stats by grid_key.
            # It aggregates event_stats by event_key.
            # It aggregates actor_stats by actor name.
            
            # The structure of _build_stats:
            # location_stats[grid_key] -> ...
            # event_stats[event_key] -> ...
            # actor_stats[actor_name] -> ...
            
            # So event/actor aggregation remains the same logic, independent of clustering method!
            # Only location_stats changes from grid_key to cluster_key.
            
            # Event Stats logic (same as original)
            eventcode = props.get("eventcode")
            category = props.get("category", "OTHER")
            actiongeo = props.get("actiongeo") or props.get("name") or "Unknown"
            if eventcode:
                event_key = f"{eventcode}|{category}|{actiongeo}"
                ev_stat = event_stats[event_key]
                ev_stat["count"] += 1
                ev_stat["weighted_count"] += 1.0
                self._accumulate_metadata(ev_stat, props, coords[i])
            
            # Actor Stats logic (same as original)
            actor1 = self._normalize_actor(props.get("actor1"))
            actor2 = self._normalize_actor(props.get("actor2"))
            if actor1:
                ac_stat = actor_stats[actor1]
                ac_stat["count"] += 1
                ac_stat["weighted_count"] += 1.0
                self._accumulate_metadata(ac_stat, props, coords[i])
            if actor2:
                ac_stat = actor_stats[actor2]
                ac_stat["count"] += 1
                ac_stat["weighted_count"] += 1.0
                self._accumulate_metadata(ac_stat, props, coords[i])

        # Calculate centroids
        self._finalize_stats(location_stats)

        return {
            "location": location_stats,
            "event": event_stats,
            "actor": actor_stats,
        }

    def _accumulate_metadata(self, stat, props, coord):
        stat["categories"][props.get("category", "OTHER")] += 1
        stat["eventcodes"][props.get("eventcode", "UNK")] += 1
        
        loc = props.get("actiongeo") or props.get("name")
        if loc: stat["locations"].add(loc)
        
        name = props.get("name")
        if name: stat["names"].add(name)
        
        self._accumulate_sources(stat, props)
        
        # Accumulate coordinates for centroid calculation
        if stat["center_lat"] is None:
            stat["center_lat"] = 0.0
            stat["center_lng"] = 0.0
        
        stat["center_lat"] += coord[0]
        stat["center_lng"] += coord[1]

    def _finalize_stats(self, stats_dict):
        # Helper to finalize centroids (average)
        for stat in stats_dict.values():
            if stat["count"] > 0 and stat["center_lat"] is not None:
                stat["center_lat"] /= stat["count"]
                stat["center_lng"] /= stat["count"]

    def _build_stats(self, features, grid_km: int):
        location_stats = defaultdict(self._empty_stat)
        event_stats = defaultdict(self._empty_stat)
        actor_stats = defaultdict(self._empty_stat)

        for feat in features:
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [None, None])
            if coords[0] is None or coords[1] is None:
                continue
            lng, lat = coords[0], coords[1]

            importance = self._safe_num(props.get("importance", 1))
            category = props.get("category") or "OTHER"
            eventcode = props.get("eventcode") or "UNKNOWN"
            actiongeo = props.get("actiongeo") or props.get("countryname") or "Unknown"
            name = props.get("name") or "Unknown"

            # Location cluster
            loc_key, center_lat, center_lng = self._grid_key(lat, lng, grid_km)
            loc_stat = location_stats[loc_key]
            loc_stat["count"] += 1
            loc_stat["weighted_count"] += importance
            loc_stat["categories"][category] += 1
            loc_stat["eventcodes"][eventcode] += 1
            loc_stat["locations"].add(actiongeo)
            loc_stat["center_lat"] = center_lat
            loc_stat["center_lng"] = center_lng
            self._accumulate_sources(loc_stat, props)

            # Event cluster
            event_key = f"{eventcode}|{category}|{actiongeo}"
            event_stat = event_stats[event_key]
            event_stat["count"] += 1
            event_stat["weighted_count"] += importance
            event_stat["categories"][category] += 1
            event_stat["eventcodes"][eventcode] += 1
            event_stat["locations"].add(actiongeo)
            event_stat["names"].add(name)
            self._accumulate_sources(event_stat, props)

            # Actor cluster
            actors = [props.get("actor1"), props.get("actor2")]
            for actor in actors:
                actor_norm = self._normalize_actor(actor)
                if not actor_norm:
                    continue
                actor_stat = actor_stats[actor_norm]
                actor_stat["count"] += 1
                actor_stat["weighted_count"] += importance
                actor_stat["categories"][category] += 1
                actor_stat["eventcodes"][eventcode] += 1
                actor_stat["locations"].add(actiongeo)
                self._accumulate_sources(actor_stat, props)

        return {
            "location": location_stats,
            "event": event_stats,
            "actor": actor_stats,
        }

    def _empty_stat(self):
        return {
            "count": 0,
            "weighted_count": 0.0,
            "categories": Counter(),
            "eventcodes": Counter(),
            "locations": set(),
            "names": set(),
            "sources": Counter(),
            "center_lat": None,
            "center_lng": None,
        }

    def _accumulate_sources(self, stat, props):
        sources = props.get("sources") or []
        for src in sources:
            url = src.get("url") if isinstance(src, dict) else None
            if url:
                stat["sources"][url] += 1

    def _safe_num(self, value):
        try:
            return float(value)
        except Exception:
            return 0.0

    def _score_and_rank(self, current_stats, previous_stats, top: int):
        ranked = []
        for key, stat in current_stats.items():
            prev = previous_stats.get(key)
            prev_count = prev["count"] if prev else 0
            current_count = stat["count"]
            if current_count == 0:
                continue
            trend = (current_count - prev_count) / max(1, prev_count)
            score = stat["weighted_count"] * (1 + trend)

            ranked.append({
                "key": key,
                "count": current_count,
                "weighted_count": round(stat["weighted_count"], 2),
                "trend": round(trend, 3),
                "score": round(score, 3),
                "categories": stat["categories"].most_common(5),
                "eventcodes": stat["eventcodes"].most_common(5),
                "locations": list(stat["locations"])[:5],
                "names": list(stat["names"])[:3],
                "top_sources": stat["sources"].most_common(5),
                "center_lat": stat["center_lat"],
                "center_lng": stat["center_lng"],
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:top]

    # ================================================================
    # ACTOR NETWORK ANALYSIS - Identify relationship patterns
    # ================================================================
    def build_actor_network(self, window_hours: int = 168, min_weight: int = 3, top_edges: int = 30, transnational: bool = False):
        """
        Build actor co-occurrence network for LLM context.
        Returns nodes (actors) and edges (interactions between actors).
        """
        from collections import Counter, defaultdict
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=window_hours)
        features = (self.firehose.history_data or {}).get("features", [])
        
        if transnational:
            features = [f for f in features if self._is_transnational(f)]
        
        edges = Counter()
        actor_counts = Counter()
        actor_categories = defaultdict(Counter)  # Track what categories each actor appears in
        actor_events = defaultdict(list)  # Track event types per actor
        
        for feat in features:
            ts = self._get_ingested_at(feat)
            if ts is None or ts < cutoff:
                continue
                
            props = feat.get("properties", {})
            actor1 = self._normalize_actor(props.get("actor1"))
            actor2 = self._normalize_actor(props.get("actor2"))
            category = props.get("category", "OTHER")
            eventcode = props.get("eventcode", "")
            
            if actor1:
                actor_counts[actor1] += 1
                actor_categories[actor1][category] += 1
                actor_events[actor1].append(eventcode)
            if actor2:
                actor_counts[actor2] += 1
                actor_categories[actor2][category] += 1
                actor_events[actor2].append(eventcode)
            
            # Build edges (co-occurrence)
            if actor1 and actor2 and actor1 != actor2:
                edge_key = tuple(sorted([actor1, actor2]))
                edges[edge_key] += 1
        
        # Filter by minimum weight and get top edges
        significant_edges = [
            {
                "source": e[0], 
                "target": e[1], 
                "weight": w,
                "strength": "strong" if w >= 10 else "medium" if w >= 5 else "weak"
            }
            for e, w in edges.most_common(top_edges)
            if w >= min_weight
        ]
        
        # Get nodes that appear in edges
        node_set = set()
        for edge in significant_edges:
            node_set.add(edge["source"])
            node_set.add(edge["target"])
        
        # Build rich node data for LLM
        nodes = []
        for actor in node_set:
            top_categories = actor_categories[actor].most_common(3)
            nodes.append({
                "id": actor,
                "count": actor_counts[actor],
                "primary_role": top_categories[0][0] if top_categories else "UNKNOWN",
                "categories": dict(top_categories),
            })
        
        # Identify key actors (high connectivity)
        node_connections = Counter()
        for edge in significant_edges:
            node_connections[edge["source"]] += edge["weight"]
            node_connections[edge["target"]] += edge["weight"]
        
        key_actors = [
            {"actor": actor, "total_interactions": count}
            for actor, count in node_connections.most_common(5)
        ]
        
        return {
            "window_hours": window_hours,
            "generated_at": now.isoformat(),
            "summary": {
                "total_actors": len(actor_counts),
                "total_edges": len(edges),
                "filtered_edges": len(significant_edges),
                "key_actors": key_actors,
            },
            "nodes": nodes,
            "edges": significant_edges,
            # LLM-optimized summary
            "llm_context": self._generate_actor_summary(key_actors, significant_edges, nodes)
        }
    
    def _generate_actor_summary(self, key_actors, edges, nodes):
        """Generate concise text summary for LLM consumption."""
        lines = []
        
        if key_actors:
            top_names = ", ".join([a["actor"] for a in key_actors[:3]])
            lines.append(f"Key actors: {top_names}")
        
        # Find strongest relationships
        strong_edges = [e for e in edges if e["strength"] == "strong"][:3]
        if strong_edges:
            relationships = [f"{e['source']} ↔ {e['target']} ({e['weight']})" for e in strong_edges]
            lines.append(f"Strong relationships: {'; '.join(relationships)}")
        
        # Category distribution
        role_counts = Counter()
        for node in nodes:
            role_counts[node["primary_role"]] += 1
        if role_counts:
            roles = ", ".join([f"{r}: {c}" for r, c in role_counts.most_common(3)])
            lines.append(f"Actor roles: {roles}")
        
        return " | ".join(lines) if lines else "No significant actor patterns detected"

    # ================================================================
    # ANOMALY DETECTION - 3-Sigma Rule
    # ================================================================
    def _load_anomaly_baseline(self):
        try:
            if not ANOMALY_BASELINE_FILE.exists():
                return {}
            data = json.loads(ANOMALY_BASELINE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_anomaly_baseline(self, baseline):
        try:
            ANOMALY_BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
            ANOMALY_BASELINE_FILE.write_text(json.dumps(baseline), encoding="utf-8")
        except Exception:
            pass

    def _update_baseline_from_history(self, daily_counts, baseline, today_str):
        for grid_key, day_data in daily_counts.items():
            stats = baseline.get(grid_key) or {"n": 0, "mean": 0.0, "M2": 0.0, "last_day": None}
            last_day = stats.get("last_day")
            for day_key in sorted(day_data.keys()):
                if day_key >= today_str:
                    continue
                if last_day and day_key <= last_day:
                    continue
                value = day_data[day_key]
                n = stats["n"] + 1
                delta = value - stats["mean"]
                mean = stats["mean"] + delta / n
                delta2 = value - mean
                M2 = stats["M2"] + delta * delta2
                stats.update(n=n, mean=mean, M2=M2, last_day=day_key)
            baseline[grid_key] = stats
        return baseline

    def detect_anomalies(self, lookback_days: int = 7, sigma_threshold: float = 2.5, transnational: bool = False):
        """
        Detect statistically significant spikes using 3-sigma rule.
        Uses a persistent per-location baseline so patterns accumulate over time.
        """
        import statistics
        
        now = datetime.now(timezone.utc)
        features = (self.firehose.history_data or {}).get("features", [])
        
        if transnational:
            features = [f for f in features if self._is_transnational(f)]
        
        # Build daily counts by location
        daily_counts = defaultdict(lambda: defaultdict(int))
        current_day_sources = defaultdict(Counter)
        location_names = {}
        
        today_str = now.strftime("%Y-%m-%d")
        
        for feat in features:
            ts = self._get_ingested_at(feat)
            if ts is None:
                continue
            
            props = feat.get("properties", {})
            geo = feat.get("geometry", {}).get("coordinates", [])
            if len(geo) < 2:
                continue
            
            # Use grid key for location
            grid_key, center_lat, center_lng = self._grid_key(geo[1], geo[0], 120)
            day_key = ts.strftime("%Y-%m-%d")
            
            daily_counts[grid_key][day_key] += 1
            
            # Collect sources for TODAY only (to explain the spike)
            if day_key == today_str:
                self._accumulate_sources({"sources": current_day_sources[grid_key]}, props)
            
            # Track location name
            if grid_key not in location_names:
                name = props.get("actiongeo") or props.get("name", "Unknown")
                location_names[grid_key] = name

        baseline = self._load_anomaly_baseline()
        baseline = self._update_baseline_from_history(daily_counts, baseline, today_str)
        self._save_anomaly_baseline(baseline)
        
        # Find anomalies
        anomalies = []
        
        for grid_key, day_data in daily_counts.items():
            current = day_data.get(today_str)
            if current is None:
                continue

            stats = baseline.get(grid_key)
            if not stats or stats.get("n", 0) < 2:
                continue

            mean = float(stats.get("mean", 0.0))
            n = int(stats.get("n", 0))
            M2 = float(stats.get("M2", 0.0))

            if n > 1 and M2 > 0:
                variance = M2 / (n - 1)
                std = variance ** 0.5 if variance > 0 else 1.0
            else:
                std = 1.0

            if std < 1:
                std = 1.0

            z_score = (current - mean) / std

            if z_score > sigma_threshold:
                top_src = current_day_sources[grid_key].most_common(5)
                formatted_sources = [{"url": url, "count": count} for url, count in top_src]

                anomalies.append({
                    "location": location_names.get(grid_key, "Unknown"),
                    "grid_key": grid_key,
                    "current_count": current,
                    "baseline_mean": round(mean, 1),
                    "baseline_std": round(std, 1),
                    "baseline_days": n,
                    "z_score": round(z_score, 2),
                    "severity": "critical" if z_score > 4 else "high" if z_score > 3 else "elevated",
                    "percent_above_normal": round((current - mean) / max(mean, 1) * 100, 1),
                    "top_sources": formatted_sources
                })
        
        # Sort by z_score
        anomalies.sort(key=lambda x: x["z_score"], reverse=True)
        
        return {
            "generated_at": now.isoformat(),
            "lookback_days": lookback_days,
            "sigma_threshold": sigma_threshold,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies[:10],
            # LLM-optimized summary
            "llm_context": self._generate_anomaly_summary(anomalies[:10])
        }
    
    def _generate_anomaly_summary(self, anomalies):
        """Generate concise anomaly summary for LLM."""
        if not anomalies:
            return "No significant anomalies detected in the monitoring period."
        
        critical = [a for a in anomalies if a["severity"] == "critical"]
        high = [a for a in anomalies if a["severity"] == "high"]
        
        parts = []
        if critical:
            locs = ", ".join([a["location"].split(",")[0] for a in critical[:3]])
            parts.append(f"CRITICAL spikes in: {locs}")
        if high:
            locs = ", ".join([a["location"].split(",")[0] for a in high[:3]])
            parts.append(f"Elevated activity in: {locs}")
        
        if anomalies:
            top = anomalies[0]
            parts.append(f"Highest: {top['location'].split(',')[0]} at {top['z_score']}σ ({top['percent_above_normal']}% above normal)")
        
        return " | ".join(parts)
