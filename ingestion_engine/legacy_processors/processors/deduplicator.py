import json
from pathlib import Path

# Basic implementation - will be expanded
class Deduplicator:
    def __init__(self, existing_events):
        self.existing_ids = set()
        self.existing_fingerprints = set()
        # Supports both v2 manifest shape (category -> [events]) and v3 (interactionsById map).
        if isinstance(existing_events, dict) and isinstance(existing_events.get("interactionsById"), dict):
            for e in existing_events["interactionsById"].values():
                if not isinstance(e, dict) or not e.get("id"):
                    continue
                self.existing_ids.add(e["id"])
                fingerprint = self._fingerprint(e)
                if fingerprint:
                    self.existing_fingerprints.add(fingerprint)
            return

        if isinstance(existing_events, dict):
            for _, events in existing_events.items():
                if not isinstance(events, list):
                    continue
                for e in events:
                    if not isinstance(e, dict) or not e.get("id"):
                        continue
                    self.existing_ids.add(e["id"])
                    fingerprint = self._fingerprint(e)
                    if fingerprint:
                        self.existing_fingerprints.add(fingerprint)

    def is_duplicate(self, event):
        if event['id'] in self.existing_ids:
            return True
        fingerprint = self._fingerprint(event)
        return fingerprint in self.existing_fingerprints if fingerprint else False

    def generate_id(self, event):
        """Generate a unique ID for the event."""
        # Slugify name + year
        base = event['name'].lower().replace(' ', '_')
        import re
        base = re.sub(r'[^a-z0-9_]', '', base)
        participants = event.get('participants_iso') or event.get('participants') or []
        participants = [p.lower() for p in participants if p]
        if participants:
            base = f"{base}_{'_'.join(sorted(participants))}"
        return base[:80]

    def _fingerprint(self, event):
        name = (event.get('name') or '').strip().lower()
        participants = event.get('participants') or event.get('participants_iso') or []
        participants = sorted([p.strip().lower() for p in participants if p])
        date = (event.get('date') or '').strip()
        if not name or not participants:
            return None
        return f"{name}|{','.join(participants)}|{date}"
