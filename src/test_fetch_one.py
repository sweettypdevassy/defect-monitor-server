#!/usr/bin/env python3
"""
Quick test: trigger a single component fetch using the new browser SW approach.
Run: docker compose exec defect-monitor python3 src/test_fetch_one.py
"""
import sys, os
sys.path.insert(0, '/app/src')

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

import yaml
with open('/app/config/config.yaml') as f:
    config = yaml.safe_load(f)

from ibm_auth import IBMAuthenticator
from defect_checker import DefectChecker

ibm = config.get('ibm', {})
auth = IBMAuthenticator(
    username=ibm.get('username', ''),
    password=ibm.get('password', ''),
    auth_method=ibm.get('auth_method', 'password'),
)

checker = DefectChecker(auth)

print("\n" + "="*60)
print("Testing fetch for component: Batch")
print("="*60 + "\n")

defects = checker.fetch_defects_for_component('Batch')

print(f"\n{'='*60}")
print(f"Result: {len(defects)} defects fetched")
if defects:
    print(f"First defect: {defects[0]}")
    print(f"Source: {defects[0].get('source','?')}")
else:
    print("No defects returned.")
print("="*60)
