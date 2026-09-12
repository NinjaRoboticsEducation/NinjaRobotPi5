"""Opt-in Chromium regression using fake responses; never connects to a robot.

Requires Playwright 1.55.0 and its Chromium browser in a test environment.
"""

import json
from itertools import product
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = (
    Path(__file__).resolve().parents[1] / "ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static"
)
SHIM = """
Object.defineProperty(navigator, 'standalone', {value:true});
Object.defineProperty(screen, 'orientation', {value:{type:'portrait-primary'}});
window.testMessages=[]; window.speechEnabled=false;
class FakeSocket extends EventTarget {
 static OPEN=1; readyState=1;
 constructor(){super();setTimeout(()=>this.emit({type:'lease',lease_id:'test',
 reconnect_token:'fake',heartbeat_seconds:10}),20);}
 emit(value){this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify(value)}));}
 send(raw){const m=JSON.parse(raw);window.testMessages.push(m);setTimeout(()=>{
 let data={};
 if(m.type==='speech'){
 if(m.operation==='on')window.speechEnabled=true;
 if(m.operation==='off')window.speechEnabled=false;data={enabled:window.speechEnabled};}
 if(m.type==='chat'){this.emit({type:'chat_delta',request_id:m.request_id,
 text:'Long response '.repeat(1400)}); data={text:'Done'};}
 this.emit({type:'result',request_id:m.request_id,data});},10);}
 close(){}
}
window.WebSocket=FakeSocket;
"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for locale, (width, height) in product(
        ["en", "ja", "zh-CN", "zh-TW"], [(390, 844), (360, 640), (600, 900), (1280, 800)]
    ):
        context = b.new_context(viewport={"width": width, "height": height}, locale=locale)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def route(r):
            path = r.request.url.split("test.local", 1)[1].split("?", 1)[0]
            file = ROOT / ("index.html" if path == "/" else path.removeprefix("/assets/"))
            if file.is_file() and ROOT in file.resolve().parents:
                r.fulfill(path=str(file))
            else:
                r.abort()

        page.route("**/*", route)
        page.add_init_script(SHIM)
        page.goto("http://test.local/")
        page.wait_for_function(
            "document.querySelector('#speechOffButton').getAttribute('aria-pressed') === 'true'"
        )
        assert page.locator(".speech-controls").count() == 0
        assert page.locator("#guideTitle").count() == 0
        initial = page.locator(".controls-panel").bounding_box()
        page.locator("#chatInput").fill("A long message " * 400)
        page.locator("#chatForm").evaluate("(el)=>el.requestSubmit()")
        page.wait_for_function(
            "document.querySelector('#chatMessages').textContent.includes('Long response')"
        )
        after = page.locator(".controls-panel").bounding_box()
        assert abs(initial["height"] - after["height"]) < 1, (initial, after)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.locator("#speechOnButton").click()
        page.wait_for_function(
            "document.querySelector('#speechOnButton').getAttribute('aria-pressed') === 'true'"
        )
        page.locator("#speechOffButton").click()
        page.wait_for_function(
            "document.querySelector('#speechOffButton').getAttribute('aria-pressed') === 'true'"
        )
        page.locator("#menuButton").click()
        page.locator("#closeMenuButton").click()
        page.set_viewport_size({"width": width, "height": 350})
        assert not page.locator(".orientation-blocker").is_visible()
        assert page.locator(".controls-panel").bounding_box()["height"] > 250
        assert not errors, errors
        assert not page.evaluate(
            "testMessages.some(x=>['behavior','move','camera','usb_microphone'].includes(x.type))"
        )
        print(
            json.dumps(
                {
                    "locale": locale,
                    "viewport": [width, height],
                    "typing_and_long_reply": "pass",
                    "speech_buttons": "pass",
                    "keyboard_resize_simulation": "pass",
                    "script_errors": errors,
                }
            )
        )
        context.close()
    b.close()
