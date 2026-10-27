from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from alpi.tools import browser

pytestmark = pytest.mark.integration


class BookingSite(BaseHTTPRequestHandler):
    authenticated_booking = False

    def reply(self, value, kind='application/json', cookie=False, status=200):
        raw = value.encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(raw)))
        if cookie:
            self.send_header('Set-Cookie','session=PRIVATE_COOKIE; HttpOnly; Path=/')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.reply('''<label>Email<input id="email"></label>
        <button onclick="fetch('/login',{method:'POST',body:JSON.stringify({email:email.value})}).then(()=>document.body.insertAdjacentHTML('beforeend','<h2>Signed in</h2>'))">Sign in</button>
        <button onclick="fetch('/booking',{method:'POST',body:JSON.stringify({amountRaw:1,email:email.value})}).then(r=>r.json()).then(r=>{if(r.status==='confirmed')document.body.insertAdjacentHTML('beforeend','<h2>Test booking confirmed</h2>')})">Confirm test booking</button>''','text/html')

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length',0)))
        if self.path == '/login':
            return self.reply('{}',cookie=True)
        type(self).authenticated_booking = 'session=PRIVATE_COOKIE' in self.headers.get('Cookie','')
        if not type(self).authenticated_booking:
            return self.reply('{}',status=403)
        self.reply('{"status":"confirmed","total":100,"bookingId":"PRIVATE_BOOKING"}')

    def log_message(self,*args):
        pass


def test_real_authenticated_booking_is_recorded_in_same_interactive_session(tmp_path,monkeypatch):
    server=ThreadingHTTPServer(('127.0.0.1',0),BookingSite)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    home=tmp_path/'home';home.mkdir()
    (home/'config.yaml').write_text(f'workspace: {json.dumps(str(tmp_path))}\ntools:\n  browser:\n    allow_local: true\n')
    monkeypatch.setenv('ALPI_HOME',str(home))
    monkeypatch.setattr(browser,'get_home',lambda:home)
    monkeypatch.setattr(browser,'HUMAN_TYPING',False)
    tool=browser.Browser()
    def call(**arguments):
        result=tool.run(**arguments)
        assert result.ok,result.error
        return result.output
    try:
        call(action='trace_start')
        call(action='navigate',url=f'http://127.0.0.1:{server.server_port}')
        call(action='type',role='textbox',name='Email',text='PRIVATE_EMAIL')
        call(action='click',role='button',name='Sign in')
        browser._on_browser_thread(lambda: browser._state['page'].get_by_role('heading',name='Signed in').wait_for())
        call(action='click',role='button',name='Confirm test booking')
        browser._on_browser_thread(lambda: browser._state['page'].get_by_role('heading',name='Test booking confirmed').wait_for())
        stopped=json.loads(call(action='trace_stop',role='heading',name='Test booking confirmed'))
        assert stopped['flow_complete'] and BookingSite.authenticated_booking
        from pathlib import Path
        text=Path(stopped['path']).read_text()
        report=json.loads(text)
        assert not any(secret in text for secret in ('PRIVATE_EMAIL','PRIVATE_COOKIE','PRIVATE_BOOKING'))
        booking=next(r for r in report['requests'] if r['path']=='/booking')
        assert booking['status']==200
        assert booking['request_body']['json']['amountRaw']==1
        assert booking['response_body']['json']['total']==100
        call(action='trace_start')
        stopped=json.loads(call(action='trace_stop',role='heading',name='Test booking confirmed'))
        assert not stopped['flow_complete']
    finally:
        tool.run(action='logout')
        server.shutdown();server.server_close()
