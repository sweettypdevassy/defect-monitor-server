#!/usr/bin/env python3
"""
Test script to verify the notification system is working correctly
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from slack_notifier import SlackNotifier

# Test data matching what the server would send
test_results = {
    "timestamp": "2026-03-14T11:05:00",
    "components": {
        "JCA": {
            "component": "JCA",
            "total": 6,
            "untriaged": 6,
            "defects": [
                {
                    "id": "12345",
                    "summary": "Test defect 1",
                    "owner": "test@ibm.com",
                    "state": "Open",
                    "triageTags": [],
                    "is_untriaged": True
                },
                {
                    "id": "12346",
                    "summary": "Test defect 2",
                    "owner": "test2@ibm.com",
                    "state": "Open",
                    "triageTags": [],
                    "is_untriaged": True
                }
            ]
        },
        "JPA": {
            "component": "JPA",
            "total": 9,
            "untriaged": 9,
            "defects": [
                {
                    "id": "12347",
                    "summary": "Test JPA defect",
                    "owner": "jpa@ibm.com",
                    "state": "Open",
                    "triageTags": [],
                    "is_untriaged": True
                }
            ]
        }
    },
    "soe_triage": {
        "total": 2,
        "defects": [
            {
                "id": "12348",
                "summary": "SOE Test defect",
                "functionalArea": "JCA",
                "filedAgainst": "Liberty/JCA",
                "ownedBy": "soe@ibm.com",
                "creationDate": "Jan 15, 2026"
            }
        ]
    },
    "total_defects": 17,
    "total_untriaged": 15,
    "monitored_components": ["JCA", "JPA"]
}

# Check which method exists
notifier = SlackNotifier("https://hooks.slack.com/test", "#test")

print("=" * 60)
print("Testing SlackNotifier Methods")
print("=" * 60)

# Check if methods exist
if hasattr(notifier, '_send_grouped_notification'):
    print("✅ _send_grouped_notification method EXISTS")
else:
    print("❌ _send_grouped_notification method MISSING")

if hasattr(notifier, '_send_component_notification'):
    print("❌ _send_component_notification method still EXISTS (should be removed)")
else:
    print("✅ _send_component_notification method removed")

print("\n" + "=" * 60)
print("Testing send_defect_notification")
print("=" * 60)

# Test the notification (will fail on webhook but we can see the logic)
try:
    notifier.send_defect_notification(test_results)
except Exception as e:
    print(f"Expected error (webhook): {e}")

print("\n✅ Test complete - check logs above")

# Made with Bob
