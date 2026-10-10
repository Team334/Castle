"""Read-only, localhost-only scouting load test using independent virtual sessions.

Run with the virtualenv Python. This signs local sessions using the local .env
secret and an EXISTING test account id; it never creates users or scouting data.
It exercises HTTP routes, rather than running 30 full browser renderers.
"""
import argparse
import csv
import ctypes
import json
import math
import os
import random
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values
from flask import Flask
from flask.sessions import SecureCookieSessionInterface

ROOT = Path(__file__).resolve().parents[1]


class StatsCells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pairs = {}
        self.rows = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'team-stats-cell' in attrs.get('class', '').split():
            number, event = attrs.get('data-team-id'), attrs.get('data-event-id')
            if number:
                self.rows += 1
                self.pairs[(number, event)] = {'team_number': number, 'event_code': event or None}


class ProcessSampler:
    """Windows process CPU and working-set samples; no extra dependencies."""
    def __init__(self, process_id):
        self.samples = []
        self.stop = threading.Event()
        self.thread = None
        self.handle = None
        if os.name != 'nt' or not process_id:
            return
        from ctypes import wintypes

        class MemoryCounters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                    'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                    'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

        self.counters = MemoryCounters
        self.filetime = wintypes.FILETIME
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.psapi = ctypes.WinDLL('psapi', use_last_error=True)
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
        self.handle = self.kernel.OpenProcess(0x0400 | 0x0010, False, process_id)
        if self.handle:
            self.sample()
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def sample(self):
        memory = self.counters()
        memory.cb = ctypes.sizeof(memory)
        times = [self.filetime() for _ in range(4)]
        if (self.psapi.GetProcessMemoryInfo(self.handle, ctypes.byref(memory), memory.cb) and
                self.kernel.GetProcessTimes(self.handle, *[ctypes.byref(value) for value in times])):
            seconds = sum((value.dwHighDateTime << 32) + value.dwLowDateTime for value in times[2:]) / 10000000
            self.samples.append({'time': time.perf_counter(),
                                 'working_set_mb': memory.WorkingSetSize / 1048576,
                                 'cpu_seconds': seconds})

    def run(self):
        while not self.stop.wait(.5):
            self.sample()

    def finish(self):
        self.stop.set()
        if not self.thread:
            return None
        self.thread.join()
        self.sample()
        self.kernel.CloseHandle(self.handle)
        duration = self.samples[-1]['time'] - self.samples[0]['time']
        return {
            'baseline_mb': round(self.samples[0]['working_set_mb'], 1),
            'peak_mb': round(max(item['working_set_mb'] for item in self.samples), 1),
            'ending_mb': round(self.samples[-1]['working_set_mb'], 1),
            'cpu_core_percent': round(100 * (self.samples[-1]['cpu_seconds'] - self.samples[0]['cpu_seconds']) / duration, 1),
            'samples': len(self.samples),
        }


def percentile(values, fraction):
    values = sorted(values)
    return round(values[max(0, math.ceil(len(values) * fraction) - 1)], 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:5000')
    parser.add_argument('--user-id', required=True, help='Existing local test account id')
    parser.add_argument('--users', type=int, default=30)
    parser.add_argument('--rounds', type=int, default=4)
    parser.add_argument('--pace', type=float, default=.1, help='Average pause between actions, seconds')
    parser.add_argument('--server-pid', type=int)
    parser.add_argument('--scenario', default='normal')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'stress-results')
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if (url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1') or
            url.username or url.password or url.path not in ('', '/') or url.query or url.fragment):
        parser.error('This test is restricted to a local HTTP server')
    if not 1 <= args.users <= 100 or not 1 <= args.rounds <= 20 or args.pace < 0:
        parser.error('Users must be 1–100, rounds 1–20, and pace nonnegative')
    secret = dotenv_values(ROOT / '.env').get('SECRET_KEY')
    if not secret:
        parser.error('The local .env must contain SECRET_KEY')
    app = Flask('castle-stress-test')
    app.secret_key = secret
    signer = SecureCookieSessionInterface().get_signing_serializer(app)
    base = args.base_url.rstrip('/')

    def session(actor):
        client = requests.Session()
        client.trust_env = False
        client.headers['Cookie'] = 'session=' + signer.dumps(
            {'_user_id': args.user_id, '_fresh': True, '_stress_actor': actor})
        return client

    # Read the existing account's visible records; no test fixtures are inserted.
    with session('preflight') as client:
        page = client.get(base + '/scouting', timeout=(3, 15), allow_redirects=False)
        if page.status_code != 200 or 'Team Data' not in page.text:
            raise SystemExit('Preflight failed: the supplied account cannot open Scout')
        cells = StatsCells()
        cells.feed(page.text)
        if not cells.pairs:
            raise SystemExit('The account needs existing scouting records for this load test')
    pairs = list(cells.pairs.values())
    events = sorted({pair['event_code'] for pair in pairs if pair['event_code']})
    year = datetime.now().year
    barrier = threading.Barrier(args.users + 1)
    rows = []
    lock = threading.Lock()
    active = 0
    peak_active = 0
    completed_users = 0
    sampler = ProcessSampler(args.server_pid)

    def actor(number):
        nonlocal active, peak_active, completed_users
        rng = random.Random(334 + number)
        event = events[number % len(events)]
        scoped_pairs = [pair for pair in pairs if pair['event_code'] == event]
        with session(number) as client:
            barrier.wait(timeout=30)

            def action(label, path, *, method='GET', payload=None, params=None, marker=None, json_type=None):
                nonlocal active, peak_active
                with lock:
                    active += 1
                    peak_active = max(peak_active, active)
                started = time.perf_counter()
                result = {'user': number, 'round': round_number, 'action': label,
                          'method': method, 'status': None, 'ms': 0, 'bytes': 0,
                          'error': '', 'pending_rows': 0, 'epa_unavailable': 0,
                          'degraded': False, 'pending_api': False}
                response = None
                try:
                    response = client.request(method, base + path, json=payload, params=params,
                                              timeout=(3, 15), allow_redirects=False)
                    result.update(status=response.status_code, bytes=len(response.content))
                    if response.status_code != 200:
                        result['error'] = f'HTTP {response.status_code}'
                    elif marker and marker not in response.text:
                        result['error'] = 'Unexpected page (possible login/error page)'
                    elif json_type:
                        body = response.json()
                        result['pending_api'] = response.headers.get('X-Scouting-Pending') == 'true'
                        if label == 'Matches' and body is None:
                            result['degraded'] = not result['pending_api']
                        elif not isinstance(body, json_type) or 'error' in body:
                            result['error'] = 'Invalid/error JSON response'
                        elif payload:
                            expected = {f"{item['team_number']}_{item['event_code']}" if item['event_code']
                                        else str(item['team_number']) for item in payload['teams']}
                            if set(body) != expected:
                                result['error'] = 'Incomplete statistics response'
                            else:
                                result['pending_rows'] = sum(bool(item.get('pending')) for item in body.values())
                                result['epa_unavailable'] = sum(item.get('epa') is None and not item.get('pending') for item in body.values())
                        elif label == 'Events':
                            result['degraded'] = not result['pending_api'] and not any(not name.startswith('Testing Regional') for name in body)
                except requests.RequestException as error:
                    result['error'] = type(error).__name__
                except (ValueError, TypeError, AttributeError) as error:
                    result['error'] = f'Validation: {type(error).__name__}'
                finally:
                    result['ms'] = round((time.perf_counter() - started) * 1000, 2)
                    with lock:
                        active -= 1
                        rows.append(result)
                if args.pace:
                    time.sleep(args.pace * rng.uniform(.5, 1.5))
                return response

            for round_number in range(1, args.rounds + 1):
                action('Scout', '/scouting', marker='Team Data')
                action('Scout statistics', '/api/team_epa_opr', method='POST',
                       payload={'teams': pairs, 'year': year}, json_type=dict)
                action('Add', '/scouting/add', marker='Add Match Scouting Data')
                response = action('Events', '/api/tba/events', params={'background': 1}, json_type=dict)
                event_key = f'{year}nyny'
                if response is not None and response.status_code == 200:
                    try:
                        event_key = (response.json().get(event) or {}).get('key') or event_key
                    except (ValueError, AttributeError):
                        pass
                action('Matches', f'/api/tba/matches/{event_key}', json_type=dict)
                action('Scout', '/scouting', marker='Team Data')
                action('Scout statistics', '/api/team_epa_opr', method='POST',
                       payload={'teams': pairs, 'year': year}, json_type=dict)
                action('Add', '/scouting/add', marker='Add Match Scouting Data')
                action('Events', '/api/tba/events', params={'background': 1}, json_type=dict)
                action('Leaderboard', '/leaderboard', params={'sort': 'opr', 'event': event}, marker='Team Leaderboard')
                action('Leaderboard statistics', '/api/team_epa_opr', method='POST',
                       payload={'teams': scoped_pairs, 'year': year}, json_type=dict)
                action('Homepage', '/', marker='<title>')
            with lock:
                completed_users += 1
                if completed_users % 5 == 0:
                    print(f'{completed_users}/{args.users} users completed; {len(rows)} requests', flush=True)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.users) as executor:
        futures = [executor.submit(actor, number) for number in range(1, args.users + 1)]
        barrier.wait(timeout=30)
        for future in futures:
            future.result()
    elapsed = time.perf_counter() - started
    memory = sampler.finish()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['action']].append(row['ms'])
    summary = {
        'scenario': args.scenario, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'virtual_users': args.users, 'rounds_per_user': args.rounds,
        'existing_records': cells.rows, 'unique_team_event_pairs': len(pairs),
        'total_requests': len(rows), 'failures': sum(bool(row['error']) for row in rows),
        'status_counts': dict(Counter(str(row['status']) for row in rows)),
        'duration_seconds': round(elapsed, 2), 'requests_per_second': round(len(rows) / elapsed, 2),
        'peak_simultaneous_requests': peak_active,
        'latency_ms': {'median': percentile([row['ms'] for row in rows], .5),
                       'p95': percentile([row['ms'] for row in rows], .95),
                       'p99': percentile([row['ms'] for row in rows], .99),
                       'max': round(max(row['ms'] for row in rows), 1)},
        'by_action': {label: {'requests': len(values), 'median_ms': percentile(values, .5),
                             'p95_ms': percentile(values, .95), 'max_ms': round(max(values), 1)}
                      for label, values in sorted(grouped.items())},
        'server_resources': memory,
        'degraded_api_responses': sum(row['degraded'] for row in rows),
        'pending_api_responses': sum(row['pending_api'] for row in rows),
        'failed_requests': [row for row in rows if row['error']],
        'scope': 'HTTP-level virtual sessions sharing one existing account; no record saves/deletes or account creation',
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.output_dir / args.scenario
    prefix.with_suffix('.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    with prefix.with_suffix('.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = [f'# Castle stress test: {args.scenario}', '',
              f'{args.users} virtual users, {args.rounds} rounds each, {len(rows)} requests.',
              f'{cells.rows} existing records; {len(pairs)} unique team/event pairs.',
              f'Failures: {summary["failures"]}; duration: {elapsed:.1f} s; throughput: {summary["requests_per_second"]} requests/s.', '',
              '| Action | Requests | Median ms | 95th percentile ms | Maximum ms |',
              '|---|---:|---:|---:|---:|']
    for label, stats in summary['by_action'].items():
        report.append(f'| {label} | {stats["requests"]} | {stats["median_ms"]} | {stats["p95_ms"]} | {stats["max_ms"]} |')
    report += ['', f'Server resources: {json.dumps(memory)}', '',
               f'Degraded API responses: {summary["degraded_api_responses"]}. Missing public statistics during an outage are expected, and are not counted as app failures.', '',
               'This test uses HTTP clients, not 30 full browsers. All sessions use one existing test account. It measures route latency including queueing and response downloads, not JavaScript rendering or real-device Wi-Fi.',
               'No account creation, scouting record saves/deletes, database migrations, or MongoDB configuration changes are performed.', '']
    prefix.with_suffix('.md').write_text('\n'.join(report), encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)
    return 1 if summary['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
