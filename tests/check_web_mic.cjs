const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/web_static/app-agent.js','utf8');
const sessions=[],events={};
class Recognition {constructor(){sessions.push(this);} start(){this.onstart();} stop(){this.stopped=true;} abort(){this.aborted=true;} }
const button={addEventListener(n,f){events[n]=f;},setAttribute(){},classList:{add(){},remove(){}},querySelector(){return {};}};
const input={value:'prefix',focus(){}};
const context={window:{SpeechRecognition:Recognition,addEventListener(){}},document:{hidden:false,addEventListener(){}},elements:{webMic:button,chatInput:input},state:{locale:'en'},SPEECH_LOCALES:{},t:x=>x,toast(){},log(){},send(){throw Error('unexpected robot capture');},stopWebMicSession:null};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('export function configureSpeechRecognition'),source.indexOf('/* ── Speech On/Off Toggle')).replace('export ',''),context);
context.configureSpeechRecognition();
const final=text=>({results:[Object.assign([{transcript:text}],{isFinal:true})]});
events.click(); const first=sessions[0];first.onresult(final('one'));assert.equal(input.value,'prefix one');
events.click();assert.equal(sessions.length,1);first.onend();assert.equal(sessions.length,2);
const second=sessions[1];first.onresult(final('stale'));assert.equal(input.value,'prefix one');
context.stopWebMicSession({abort:true});input.value='';second.onresult(final('late'));assert.equal(input.value,'');
events.click();assert.equal(sessions.length,2);second.onend();assert.equal(sessions.length,3);
const third=sessions[2];third.onresult(final('three'));events.click();context.stopWebMicSession({abort:true});third.onend();assert.equal(sessions.length,3);
events.click();assert.equal(sessions.length,4);console.log('PASS repeated dictation, queued restart, stale events and submission cancellation');
