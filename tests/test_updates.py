"""Panel version/checker tests never contact GitHub or use checkout data."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading

import pytest
import requests

from beammpy import updates
from beammpy.updates import UpdateChecker
from beammpy.versioning import VERSION, is_newer, manifest_version, semver
from conftest import headers


@pytest.mark.parametrize(('local', 'published', 'expected'), [
    ('0.4.1', '0.4.2', True), ('0.4.1', '0.4.1', False), ('0.5.0', '0.4.2', False),
    ('0.9.9', '0.10.0', True), ('1.0.0-rc.1', '1.0.0', True),
    ('1.0.0', '1.0.0-rc.1', False), ('1.0.0-beta.2', '1.0.0-beta.11', True),
    ('1.0.0-beta.11', '1.0.0-rc.1', True), ('1.0.0-alpha', '1.0.0-alpha.1', True),
    ('1.0.0-alpha.1', '1.0.0-alpha.beta', True), ('1.0.0-1', '1.0.0-alpha', True),
    ('1.0.0+old', '1.0.0+new', False), ('1.0.0-rc.1+a', '1.0.0-rc.1+b', False),
])
def test_semver_ordering(local, published, expected):
    assert is_newer(published, local) is expected


@pytest.mark.parametrize('value', ['v1.0.0', '1.0', '01.0.0', '1.0.0-01', '1.0.0-a..b',
                                  '1.0.0+', '1.0.0-β', ' 1.0.0', '1.0.0\n', '', None, 123])
def test_invalid_versions(value):
    with pytest.raises(ValueError):
        semver(value)


def finish(checker):
    checker._worker.join(timeout=5)
    assert not checker._worker.is_alive()
    return checker.snapshot()


@pytest.mark.parametrize('published', ['0.4.2', '0.4.1', '0.3.0', '0.4.2-rc.1', '0.4.1+build.2'])
def test_availability_and_success_cache(published):
    now, calls = [100], []
    checker = UpdateChecker(installed='0.4.1', fetch=lambda: calls.append(1) or published, clock=lambda: now[0])
    assert calls == []  # Construction/startup is offline.
    assert checker.snapshot()['status'] == 'checking'
    result = finish(checker)
    assert result['installed_version'] == '0.4.1'
    assert result['update_available'] == is_newer(published, '0.4.1')
    for _ in range(10):
        assert checker.snapshot() == result
    now[0] += updates.SUCCESS_TTL - 1
    checker.snapshot()
    assert len(calls) == 1
    now[0] += 2
    assert checker.snapshot()['status'] == 'checking'
    finish(checker)
    assert len(calls) == 2


@pytest.mark.parametrize('error', [requests.Timeout(), requests.ConnectionError(), ValueError(), TypeError(), OSError()])
def test_failures_are_silent_and_negatively_cached(error):
    now, calls = [100], []
    def fetch():
        calls.append(1)
        raise error
    checker = UpdateChecker(fetch=fetch, clock=lambda: now[0])
    checker.snapshot()
    result = finish(checker)
    assert result['status'] == 'unavailable'
    assert not result['update_available'] and result['available_version'] is None
    for _ in range(10):
        checker.snapshot()
    now[0] += updates.FAILURE_TTL - 1
    checker.snapshot()
    assert len(calls) == 1
    now[0] += 2
    checker.snapshot(); finish(checker)
    assert len(calls) == 2


def test_concurrent_checks_share_one_request_and_failed_refresh_clears_notice():
    calls, now, gate = [], [100], threading.Event()
    def fetch():
        calls.append(1)
        assert gate.wait(timeout=5)
        return '9.0.0'
    checker = UpdateChecker(fetch=fetch, clock=lambda: now[0])
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: checker.snapshot(), range(20)))
    assert all(item['status'] == 'checking' and not item['update_available'] for item in results)
    gate.set()
    assert finish(checker)['update_available'] and calls == [1]
    checker._fetch = lambda: 'invalid'
    now[0] += updates.SUCCESS_TTL + 1
    assert not checker.snapshot()['update_available']
    assert finish(checker)['available_version'] is None


class Response:
    def __init__(self, body=b'{"version":"1.0.0"}', *, status=200, headers=None):
        self.body, self.status_code = body, status
        self.headers = {'Content-Type': 'text/plain; charset=utf-8', **(headers or {})}
        self.closed = False

    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    def iter_content(self, chunk_size):
        yield from (self.body[i:i+chunk_size] for i in range(len(self.body)))


def test_http_limits_and_fixed_url(monkeypatch):
    response = Response()
    def get(url, **kwargs):
        assert url == updates.MANIFEST_URL
        assert kwargs['timeout'] == (2, 3) and kwargs['stream']
        assert kwargs['allow_redirects'] is False
        return response
    monkeypatch.setattr(updates.requests, 'get', get)
    assert updates.fetch_version() == '1.0.0' and response.closed


@pytest.mark.parametrize('response', [
    Response(status=404), Response(status=302), Response(b'<html>no</html>'),
    Response(b'{broken'), Response(b'{"version":123}'), Response(b'{"version":"01.0.0"}'),
    Response(b'{"version":"1.0.0", "command":"untrusted"}'), Response(b'[]'),
    Response(b'\xff'), Response(b' ' * (updates.MAX_BYTES + 1)),
    Response(b'{"version":"1.0.0","version":"9.0.0"}'), Response(b'[' * 2000 + b']' * 2000),
    Response(headers={'Content-Length': str(updates.MAX_BYTES + 1)}),
    Response(headers={'Content-Length': 'bad'}), Response(headers={'Content-Type': 'text/html'}),
])
def test_malformed_unavailable_and_oversized_responses(monkeypatch, response):
    monkeypatch.setattr(updates.requests, 'get', lambda *args, **kwargs: response)
    with pytest.raises(ValueError):
        updates.fetch_version()
    assert response.closed


def test_slow_response_body_deadline(monkeypatch):
    now = iter([0, 1, 9])
    monkeypatch.setattr(updates.time, 'monotonic', lambda: next(now))
    monkeypatch.setattr(updates.requests, 'get', lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match='limits'):
        updates.fetch_version()


@pytest.mark.parametrize(('platform', 'host', 'command'), [
    ('win32', 'windows', updates.WINDOWS_COMMAND), ('linux', 'linux', updates.UBUNTU_COMMAND),
    ('darwin', 'unsupported', None),
])
def test_host_os_command_and_readme_agree(platform, host, command):
    checker = UpdateChecker(host_os=platform, fetch=lambda: VERSION)
    result = checker.snapshot(); finish(checker)
    assert result['host_os'] == host and result['command'] == command
    if command:
        readme = (Path(__file__).resolve().parents[1] / 'README.md').read_text(encoding='utf-8')
        assert readme.count(command) == 2


def test_authenticated_read_only_metadata_preserves_member_permissions(app, client):
    checker = UpdateChecker(host_os='linux', fetch=lambda: '9.0.0')
    app.extensions['updates'] = checker
    assert app.test_client().get('/api/panel/update').status_code == 401
    assert checker._worker is None
    assert client.post('/api/users', json={'username': 'update-member', 'password': 'member888',
                        'temporary': False, 'permissions': {}}, headers=headers(client)).status_code == 201
    member = app.test_client()
    assert member.post('/api/auth/login', json={'username': 'update-member', 'password': 'member888'}, headers=headers(member)).status_code == 200
    response = member.get('/api/panel/update', headers={'User-Agent': 'Windows browser'})
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    finish(checker)
    response = member.get('/api/panel/update').json
    assert response['update_available'] and response['host_os'] == 'linux'
    assert response['command'] == updates.UBUNTU_COMMAND
    assert member.get('/api/users').status_code == 403
    assert member.post('/api/panel/update', json={}, headers=headers(member)).status_code == 405
