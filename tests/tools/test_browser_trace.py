from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from alpi.tools import browser
from alpi.tools import _browser_trace as tracing


@pytest.fixture
def trace(monkeypatch, tmp_path):
    monkeypatch.setattr(tracing, 'resolve_workspace_path', lambda p, **kw: tmp_path / p if not str(p).startswith('/') else __import__('pathlib').Path(p))
    context = MagicMock()
    return tracing.BrowserTrace(context)


def test_trace_records_request_response_and_confirmation_without_credentials(trace):
    request = MagicMock()
    request.url = 'https://example.com/booking/123456?token=SECRET&email=PRIVATE'
    request.method = 'POST'
    request.resource_type = 'fetch'
    request.post_data_buffer = b'{"email":"PRIVATE","amountRaw":100,"currency":"EUR","bookingId":"id-123"}'
    response = request.response.return_value
    response.status = 201
    raw = b'{"status":"confirmed","bookingId":"id-123","token":"SECRET"}'
    response.headers = {'content-type':'application/json','content-length':str(len(raw)), 'set-cookie':'PRIVATE'}
    response.body.return_value = raw
    trace.step('navigate', True)
    trace.request(request)
    trace.finished(request)
    assert trace.close(True)['flow_complete']
    saved = trace.path.read_text()
    data = json.loads(saved)
    assert 'SECRET' not in saved and 'PRIVATE' not in saved and 'set-cookie' not in saved
    row = data['requests'][0]
    assert row['path'] == '/booking/:value'
    assert row['request_body']['json']['amountRaw'] == 100
    assert row['request_body']['json']['bookingId'] == row['response_body']['json']['bookingId']
    assert trace.path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('navigation,confirmation,failed', [(False,True,False),(True,False,False),(True,True,True)])
def test_partial_or_failed_workflow_never_becomes_complete(trace,navigation,confirmation,failed):
    if navigation: trace.step('navigate',True)
    if failed: trace.step('click',False)
    assert not trace.close(confirmation)['flow_complete']


def test_body_budget_and_record_limit_are_explicit(trace,monkeypatch):
    trace.body_bytes = 4 * 1024 * 1024
    assert 'omitted' in trace.body(b'{"total":100}')
    monkeypatch.setattr(tracing,'_LIMIT',0)
    trace.request(MagicMock())
    assert trace.truncated and not trace.rows


def test_browser_actions_stay_in_recorded_context(monkeypatch,trace):
    page = MagicMock()
    page.url='https://example.com/'
    page.locator.return_value.aria_snapshot.return_value='Page'
    monkeypatch.setattr(browser,'_on_browser_thread',lambda fn:fn())
    monkeypatch.setattr(browser,'_ensure_page_blocking',lambda:(page,None))
    monkeypatch.setitem(browser._state,'trace',trace)
    monkeypatch.setitem(browser._state,'page',page)
    result=browser.Browser().run('click',role='button',name='Confirm')
    assert result.ok
    page.get_by_role.assert_called_once_with('button',name='Confirm')
    assert trace.steps[-1]['action']=='click'
    page.get_by_role.return_value.first.is_visible.return_value=True
    result=browser.Browser().run('trace_stop',role='heading',name='Confirmed')
    assert result.ok and json.loads(result.output)['confirmation_observed']
    page.get_by_role.assert_called_with('heading',name='Confirmed',exact=True)
    assert browser._state['trace'] is None


def test_invalid_browser_action_prevents_a_successful_flow(monkeypatch, trace):
    monkeypatch.setattr(browser,'_on_browser_thread',lambda fn:fn())
    monkeypatch.setitem(browser._state,'trace',trace)
    trace.step('navigate',True)
    result=browser.Browser().run('type',role='textbox')
    assert not result.ok
    assert trace.steps[-1] == {'action':'type','ok':False,'ms':trace.steps[-1]['ms']}
    assert not trace.close(True)['flow_complete']


def _request(kind='xhr', url='https://example.com/api/pay'):
    request = MagicMock()
    request.url = url
    request.method = 'POST'
    request.resource_type = kind
    request.post_data_buffer = b''
    return request


@pytest.mark.parametrize('kind,status', [('xhr', 500), ('fetch', 404), ('document', 403)])
def test_an_error_response_blocks_completion(trace, kind, status):
    request = _request(kind)
    request.response.return_value.status = status
    request.response.return_value.headers = {}
    trace.step('navigate', True)
    trace.request(request)
    trace.finished(request)
    assert not trace.close(True)['flow_complete']


def test_a_failed_request_blocks_completion(trace):
    request = _request('document')
    trace.step('navigate', True)
    trace.request(request)
    trace.failed(request)
    assert not trace.close(True)['flow_complete']


def test_a_write_error_marks_the_trace_incomplete_without_failing_the_action(trace, monkeypatch):
    trace.step('navigate', True)
    monkeypatch.setattr(trace, 'save', MagicMock(side_effect=OSError('disk full')))
    trace.step('click', True)
    assert trace.error and trace.steps[-1]['action'] == 'click' and trace.steps[-1]['ok']
    assert not trace.report()['flow_complete']


def test_saving_does_not_resolve_the_path_again(trace, monkeypatch):
    monkeypatch.setattr(tracing, 'resolve_workspace_path', MagicMock(side_effect=ValueError('other workspace')))
    trace.step('navigate', True)
    assert not trace.error


def test_a_failed_action_is_recorded_once(monkeypatch, trace):
    monkeypatch.setitem(browser._state, 'trace', trace)
    monkeypatch.setattr(browser, '_on_browser_thread', lambda fn: fn())
    monkeypatch.setattr(browser.Browser, '_run_action', lambda self, *a: browser.ToolResult(ok=False, output='', error='x'))
    browser.Browser().run('click')
    assert [s['action'] for s in trace.steps] == ['click']
