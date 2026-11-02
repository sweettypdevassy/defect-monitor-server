#!/usr/bin/env python3
"""
Read-only probe: show which date/state fields RTC returns for closed defects.
Usage: python3 probe_closed_defect_fields.py 307958 308600 308744
Needs only: requests, urllib3, pyyaml (no numpy / ML deps).
"""

import re
import sys
sys.path.insert(0, 'src')

import yaml
from ibm_auth import IBMAuthenticator

ids = sys.argv[1:] or ['307958', '308600', '308744']

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

auth = IBMAuthenticator(
    username=config['ibm']['username'],
    password=config['ibm']['password'],
    auth_method='password'
)

date_re = re.compile(r'^\d{4}-\d{2}-\d{2}T')

for defect_id in ids:
    session = auth.get_session()
    if not session:
        print("Authentication failed")
        sys.exit(1)
    url = f"https://wasrtc.hursley.ibm.com:9443/jazz/oslc/workitems/{defect_id}.json"
    data = session.get(url, timeout=60, headers={'Accept': 'application/json'}, verify=False).json()

    print(f"\n=== {defect_id} ===")
    for key, value in data.items():
        text = str(value)
        if date_re.match(text) or 'state' in key.lower() or 'resol' in key.lower() or 'modified' in key.lower():
            print(f"  {key}: {text[:150]}")
