"""Spaced probe of the live Pinterest flow: python tools/probe_pinterest.py https://your-site.example [seconds-between-calls]"""
import sys
import time

import requests

SITE = sys.argv[1].rstrip('/')
GAP = float(sys.argv[2]) if len(sys.argv) > 2 else 12
LINKS = ['https://pin.it/1Llt9HRdp', 'https://pin.it/55aPD5MCW', 'https://pin.it/1DdlFsoPF', 'https://pin.it/1nAsJSkh2', 'https://pin.it/49lpVB04J']

for link in LINKS:
    started = time.time()
    response = requests.post(f'{SITE}/api/info', json={'url': link, 'ack': True}, timeout=120)
    try:
        body = response.json()
    except ValueError:
        body = {'raw': response.text[:120]}
    kinds = [a['kind'] for a in body.get('assets', [])]
    print(f'{link} -> HTTP {response.status_code} in {time.time() - started:.1f}s {kinds or body.get("error") or body}')
    time.sleep(GAP)
