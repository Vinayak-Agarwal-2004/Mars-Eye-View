"""
Optional Prefect orchestration layer for GDELT pipeline.
Install with: pip install prefect

This module provides workflow orchestration for the GDELT ingestion pipeline.
It's optional and can be used if workflow complexity increases.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from prefect import flow, task
    from prefect.schedules import IntervalSchedule
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    print("[Orchestration] Prefect not installed. Install with: pip install prefect")


if PREFECT_AVAILABLE:
    @task(retries=3, retry_delay_seconds=60)
    def ingest_gdelt_data():
        """Task to ingest new GDELT data"""
        from server.app.services.firehose import FirehoseService
        
        firehose = FirehoseService()
        firehose._fetch_cycle()
        
        checkpoint = firehose.checkpoint_manager.get_state()
        return {
            'processed_count': checkpoint.get('processed_count', 0),
            'last_timestamp': checkpoint.get('last_timestamp')
        }

    @task
    def analyze_patterns(data):
        """Task to analyze patterns and detect hotspots"""
        from server.app.services.firehose import FirehoseService
        from server.app.services.hotspot import HotspotAnalyzer
        
        firehose = FirehoseService()
        analyzer = HotspotAnalyzer(firehose)
        
        hotspots = analyzer.analyze(
            window_hours=168,
            previous_hours=720,
            grid_km=120,
            top=10
        )
        
        anomalies = analyzer.detect_anomalies(lookback_days=7, sigma_threshold=2.5)
        
        return {
            'hotspots': hotspots,
            'anomalies': anomalies
        }

    @task
    def detect_anomalies(metrics):
        """Task to detect anomalies and send alerts"""
        from server.app.services.alerting import AlertingService
        
        alerting = AlertingService()
        
        anomalies = metrics.get('anomalies', {}).get('anomalies', [])
        if anomalies:
            alerting.send_anomaly_alert(anomalies)
        
        return {
            'anomalies_detected': len(anomalies),
            'alerts_sent': len([a for a in anomalies if a.get('severity') == 'critical'])
        }

    @task
    def process_conflict_events():
        """Task to process conflict events"""
        try:
            from ingestion_engine.conflict_monitor import ConflictMonitor
            from server.app.services.firehose import FirehoseService
            
            firehose = FirehoseService()
            if not firehose.history_data.get("features"):
                return {'conflict_events': 0, 'alerts': []}
            
            monitor = ConflictMonitor()
            result = monitor.process_events(firehose.history_data["features"])
            
            return result
        except Exception as e:
            print(f"[Orchestration] Conflict processing failed: {e}")
            return {'conflict_events': 0, 'alerts': []}

    @task
    def process_diplomatic_relations():
        """Task to process diplomatic relations"""
        try:
            from ingestion_engine.diplomatic_tracker import DiplomaticRelationsTracker
            from server.app.services.firehose import FirehoseService
            
            firehose = FirehoseService()
            if not firehose.history_data.get("features"):
                return {'bilateral': 0}
            
            tracker = DiplomaticRelationsTracker()
            result = tracker.process_events(firehose.history_data["features"])
            
            return result
        except Exception as e:
            print(f"[Orchestration] Diplomatic processing failed: {e}")
            return {'bilateral': 0}

    @flow(name="gdelt-rolling-pipeline")
    def gdelt_pipeline():
        """Main Prefect flow for GDELT pipeline"""
        data = ingest_gdelt_data()
        metrics = analyze_patterns(data)
        anomaly_results = detect_anomalies(metrics)
        conflict_results = process_conflict_events()
        diplomacy_results = process_diplomatic_relations()
        
        return {
            'ingestion': data,
            'analysis': metrics,
            'anomalies': anomaly_results,
            'conflicts': conflict_results,
            'diplomacy': diplomacy_results
        }

    def create_schedule():
        """Create Prefect schedule for GDELT pipeline"""
        schedule = IntervalSchedule(interval=timedelta(minutes=15))
        return schedule

    def deploy_flow():
        """Deploy the Prefect flow"""
        if not PREFECT_AVAILABLE:
            print("[Orchestration] Prefect not available. Install with: pip install prefect")
            return
        
        schedule = create_schedule()
        
        print("[Orchestration] To deploy this flow:")
        print("1. Start Prefect server: prefect server start")
        print("2. Create deployment: prefect deployment build orchestration.py:gdelt_pipeline")
        print("3. Apply deployment: prefect deployment apply gdelt_pipeline")
        print(f"4. Schedule: Every 15 minutes")

else:
    def gdelt_pipeline():
        """Fallback when Prefect is not available"""
        print("[Orchestration] Prefect not installed. Using direct execution.")
        from server.app.services.firehose import FirehoseService
        
        firehose = FirehoseService()
        firehose._fetch_cycle()
        
        return {'status': 'completed', 'mode': 'direct'}


if __name__ == '__main__':
    if PREFECT_AVAILABLE:
        result = gdelt_pipeline()
        print(f"[Orchestration] Pipeline completed: {result}")
    else:
        print("[Orchestration] Prefect not installed. Install with: pip install prefect")
        print("[Orchestration] Running direct execution mode...")
        result = gdelt_pipeline()
        print(f"[Orchestration] Completed: {result}")
