from pathlib import Path
import json,hashlib,subprocess,xml.etree.ElementTree as ET,datetime
lane=Path(__file__).resolve().parent.parent;ev=lane/'evidence';stage=lane.parent.parent/'publish/netty-codexcoder21-2'
names=['testProtocolRootCloseAfterShutdownStartedInEventLoopClosesRoot']+['testProtocolRootCloseCallerRacingEventLoopShutdown']*10+['testGracefulCloseEmitsSingleDisconnectedEvent','testConnectionListenerIsolation']
r=json.loads((ev/'url-verification-results.json').read_text()) if (ev/'url-verification-results.json').exists() else []
assert [x['name'] for x in r]==names[:len(r)]
origin=json.loads((ev/'runtime-origin-result.json').read_text()) if (ev/'runtime-origin-result.json').exists() else {'passed':False}
original=json.loads((ev/'upstream-cache-hashes-before.json').read_text());after={p:hashlib.sha256((lane/p).read_bytes()).hexdigest() for p in original};assert original==after,'Upstream-coordinate cache bytes changed'
(ev/'upstream-cache-hashes-after.json').write_text(json.dumps(after,indent=2)+'\n')
ready=origin['passed'] and len(r)==13 and all(x['gate_ok'] for x in r)
status='PUBLISH-READY' if ready else 'HOLD'
lines=[status,'Version: 4.2.10.1-codexcoder21','No artifacts have been published.','Runtime custom transport/buffer/common origins: '+('PASS' if origin['passed'] else 'NOT PASSED'),f'Consumer invocations: {sum(x["gate_ok"] for x in r)}/13 passed; {sum(not x["gate_ok"] for x in r)} failed; {13-len(r)} unrun.','Upstream-coordinate cache JARs unchanged: '+str(len(original)),'Results:']
for i,name in enumerate(names,1):
 result=next((x for x in r if x['index']==i),None)
 lines.append(f'{i:02d}. {name}: '+('PASS' if result and result['gate_ok'] else 'FAIL' if result else 'UNRUN')+(f' ({result["seconds"]}s)' if result else ''))
for x in r:
 if not x['gate_ok'] and Path(x['xml']).exists():
  stacks=[t.findtext('stacktrace','') for t in ET.parse(x['xml']).getroot().findall('test')]
  (ev/f'url-{x["index"]:02d}-full-stack.txt').write_text('\n\n'.join(stacks))
  with (lane.parent.parent/'out/r146-findings.md').open('a') as f:f.write('\nOBSERVED full failing consumer stack:\n```\n'+'\n\n'.join(stacks)+'\n```\n')
text='\n'.join(lines)+'\n';(ev/'STATUS.txt').write_text(text)
if stage.exists():(stage/'STATUS.txt').write_text(text)
(ev/'gate-summary.json').write_text(json.dumps(dict(status=status,passed=sum(x['gate_ok'] for x in r),failed=sum(not x['gate_ok'] for x in r),unrun=13-len(r),origin=origin,upstream_jars_unchanged=len(original)),indent=2)+'\n')
print(text)
