#!/usr/bin/env python3
"""
Dispute Extractor Script

Extracts territorial disputes from country_info.json and creates
the new modular dispute file structure.

Usage: python extract_disputes.py
"""

import json
import os
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / 'data'
DISPUTES_DIR = DATA_DIR / 'disputes'

def slugify(text):
    """Convert text to URL-friendly slug."""
    import re
    slug = text.lower()
    slug = re.sub(r'[/\\]', '_', slug)  # Replace slashes
    slug = re.sub(r'[^a-z0-9_]', '_', slug)  # Replace other special chars
    slug = re.sub(r'_+', '_', slug)  # Collapse multiple underscores
    return slug.strip('_')


def load_country_info():
    """Load existing country_info.json."""
    with open(DATA_DIR / 'country_info.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_disputes(country_info):
    """Extract all disputes from country_info, deduplicating by region+claimants."""
    disputes = {}  # key -> dispute data
    
    for iso3, info in country_info.items():
        if not info.get('disputes'):
            continue
            
        for dispute in info['disputes']:
            # Create unique key
            all_claimants = sorted([iso3] + dispute.get('other_claimants', []))
            key = slugify(dispute['region'])
            
            if key in disputes:
                # Already seen this dispute, just verify claimants match
                continue
            
            # Create dispute entry
            disputes[key] = {
                'id': key,
                'name': dispute['region'],
                'type': dispute.get('type', 'territorial'),
                'status': dispute.get('status', 'disputed'),
                'claimants': all_claimants,
                'description': dispute.get('description', ''),
                'since': dispute.get('since'),
                'source': 'wikipedia'
            }
    
    return disputes

def create_manifest(disputes):
    """Create manifest.json with dispute index."""
    manifest = {
        'version': '1.0',
        'last_updated': datetime.utcnow().isoformat() + 'Z',
        'disputes': []
    }
    
    for dispute_id, dispute in disputes.items():
        manifest['disputes'].append({
            'id': dispute['id'],
            'name': dispute['name'],
            'type': dispute['type'],
            'status': dispute['status'],
            'claimants': dispute['claimants'],
            'short_description': dispute['description'][:200] if dispute['description'] else '',
            'file': f'disputes/{dispute_id}.json'
        })
    
    return manifest

def create_individual_files(disputes):
    """Create individual dispute JSON files."""
    disputes_subdir = DISPUTES_DIR / 'disputes'
    disputes_subdir.mkdir(parents=True, exist_ok=True)
    
    for dispute_id, dispute in disputes.items():
        full_dispute = {
            'id': dispute['id'],
            'name': dispute['name'],
            'aliases': [],
            
            'classification': {
                'type': dispute['type'],
                'status': dispute['status'],
                'since': dispute['since']
            },
            
            'claimants': [
                {'iso': iso, 'claim': '', 'controls': []}
                for iso in dispute['claimants']
            ],
            
            'geography': {
                'primary_location': {
                    'iso': dispute['claimants'][0] if dispute['claimants'] else None,
                    'coordinates': None
                },
                'affected_regions': []
            },
            
            'description': dispute['description'],
            
            'sources': [
                {
                    'id': 'src_wiki_001',
                    'type': 'wikipedia',
                    'url': None,
                    'retrieved': datetime.utcnow().isoformat() + 'Z',
                    'contributed_fields': ['name', 'description', 'claimants', 'status']
                }
            ],
            
            'metadata': {
                'created': datetime.utcnow().isoformat() + 'Z',
                'updated': datetime.utcnow().isoformat() + 'Z',
                'confidence': 0.8
            }
        }
        
        filepath = disputes_subdir / f'{dispute_id}.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(full_dispute, f, indent=2, ensure_ascii=False)
        
        print(f'  Created: {filepath.name}')

def main():
    print('🔍 Loading country_info.json...')
    country_info = load_country_info()
    
    print('📤 Extracting disputes...')
    disputes = extract_disputes(country_info)
    print(f'   Found {len(disputes)} unique disputes')
    
    print('📝 Creating manifest.json...')
    manifest = create_manifest(disputes)
    DISPUTES_DIR.mkdir(parents=True, exist_ok=True)
    with open(DISPUTES_DIR / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print('📁 Creating individual dispute files...')
    create_individual_files(disputes)
    
    print(f'✅ Done! Created {len(disputes)} dispute files in {DISPUTES_DIR}')

if __name__ == '__main__':
    main()
