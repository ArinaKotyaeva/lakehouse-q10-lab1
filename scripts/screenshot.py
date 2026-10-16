"""Optional real-browser screenshots (requires installed Edge and websockets)."""
import base64,json,subprocess,tempfile,time,urllib.request
from pathlib import Path
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parents[1]
profile=tempfile.mkdtemp(prefix='lab1-q10-edge-')
proc=subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe','--headless=new','--disable-gpu','--no-first-run','--remote-debugging-port=9225','--remote-allow-origins=http://localhost:9225','--user-data-dir='+profile,'about:blank'],creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for _ in range(60):
 try:
  with urllib.request.urlopen('http://localhost:9225/json/list',timeout=2) as r: pages=json.load(r)
  break
 except Exception: time.sleep(.5)
page=next(p for p in pages if p['type']=='page')
with connect(page['webSocketDebuggerUrl'],origin='http://localhost:9225',max_size=20_000_000) as ws:
 counter=0
 def cmd(method,params=None):
  global counter
  counter+=1; ident=counter; ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
  while True:
   m=json.loads(ws.recv(timeout=90))
   if m.get('id')==ident:
    if 'error' in m: raise RuntimeError(m['error'])
    return m.get('result',{})
 def evaluate(expr): return cmd('Runtime.evaluate',{'expression':expr,'returnByValue':True}).get('result',{}).get('value')
 def wait(expr):
  for _ in range(120):
   if evaluate(expr): return
   time.sleep(.5)
  raise RuntimeError('UI did not finish rendering: '+str(evaluate('document.body.innerText')))
 cmd('Page.enable'); cmd('Emulation.setDeviceMetricsOverride',{'width':1600,'height':1800,'deviceScaleFactor':1,'mobile':False})
 cmd('Page.navigate',{'url':'http://localhost:18088'})
 wait("document.querySelectorAll('[data-testid=stDataFrame]').length>=2")
 time.sleep(2)
 for filename in ['bronze-ui.png','gold-ui.png']:
  if filename.startswith('gold'):
   evaluate("Array.from(document.querySelectorAll('label')).find(x=>x.innerText.trim()==='Gold').click()")
   wait("document.querySelectorAll('[data-testid=stDataFrame]').length===1 && document.body.innerText.includes('Топ-20')")
   time.sleep(2)
  data=cmd('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})
  (ROOT/'results'/filename).write_bytes(base64.b64decode(data['data']))
  print('Saved',filename,flush=True)
 try: cmd('Browser.close')
 except Exception: pass
