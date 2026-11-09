const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-shared.js', 'utf8');
const sockets = [], timers = new Map(), page = {}, messages = [];
let timerId = 0, rejected = 0, probeStatus = 405;
class Socket {
  static OPEN = 1; static CLOSING = 2;
  constructor() { this.readyState = 0; this.events = {}; sockets.push(this); }
  addEventListener(name, fn) { this.events[name] = fn; }
  close() { this.readyState = 2; }
}
const state = {socket:null, departed:false, reconnectTimer:null, pending:new Map(), controllerStarted:true,
  browserChatId:'browser-identity', reconnectToken:'saved-token', lockedRetries:0};
const window = {location:{protocol:'https:',host:'robot.example'},
  addEventListener(name, fn) {page[name] = fn;},
  clearTimeout(id) {timers.delete(id);}, clearInterval(){},
  setTimeout(fn) {const id = ++timerId; timers.set(id, fn); return id;}};
const context = {state, window, WebSocket:Socket, URLSearchParams, AbortSignal,
  messageHandlers:{onClose(){}}, updatePoweroffAvailability(){}, setConnection(){},
  t:x=>x, log(){}, toast(){}, handleMessage(message){messages.push(message);},
  fetch:async()=>({status:probeStatus})};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('export function connect()'),source.indexOf('function handleMessage')).replace('export ',''), context);
const lifecycle = source.slice(source.indexOf('  window.addEventListener("pagehide"'),source.indexOf('  initSharedActions();'));
vm.runInContext(lifecycle, context);
(async () => {
  context.connect(); context.connect(); assert.equal(sockets.length,1);
  const first = sockets[0]; first.readyState = 1;
  state.pending.set('one', {reject(){rejected++;}});
  page.pagehide(); assert.equal(rejected,1); assert.equal(first.readyState,2);
  page.pageshow(); assert.equal(sockets.length,2);
  const second = sockets[1];
  await first.events.close({code:1000}); first.events.message({data:'{"stale":true}'});
  assert.equal(messages.length,0); assert.equal(state.socket,second); assert.equal(timers.size,0);
  second.readyState = 3;
  state.pending.set('two', {reject(){rejected++;}});
  await second.events.close({code:1006});
  assert.equal(rejected,2); assert.equal(timers.size,1);
  const retry = [...timers.values()][0]; timers.clear(); retry();
  assert.equal(sockets.length,3); assert.equal(timers.size,0);
  const third = sockets[2]; third.readyState = 3; probeStatus = 401;
  await third.events.close({code:1006}); assert.equal(timers.size,0);
  context.connect(); const fourth = sockets[3]; fourth.readyState = 3;
  await fourth.events.close({code:4423}); assert.equal(timers.size,1);
  page.pagehide(); assert.equal(timers.size,0);
  page.pageshow(); assert.equal(sockets.length,5);
  console.log('PASS one socket/timer, departure, BFCache, stale events, pending requests, pairing and lock retry');
})().catch(error=>{console.error(error);process.exitCode=1;});
