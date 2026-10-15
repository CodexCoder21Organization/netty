from pathlib import Path
import subprocess,os,time,json,datetime,signal,xml.etree.ElementTree as ET
lane=Path(__file__).resolve().parent.parent;repo=lane/'workspace/UrlProtocol-verification';evidence=lane/'evidence'
names=['testProtocolRootCloseAfterShutdownStartedInEventLoopClosesRoot']+['testProtocolRootCloseCallerRacingEventLoopShutdown']*10+['testGracefulCloseEmitsSingleDisconnectedEvent','testConnectionListenerIsolation']
env=os.environ.copy();env.update(JAVA_HOME='/usr/lib/jvm/temurin-21-jdk-amd64',COURSIER_CACHE=str(lane/'coursier-cache'),COURSIER_ARCHIVE_CACHE=str(lane/'coursier-archives'),COURSIER_JVM_CACHE=str(lane/'coursier-jvm'),JAVA_TOOL_OPTIONS='-Xmx2g',PATH='/usr/lib/jvm/temurin-21-jdk-amd64/bin:'+env['PATH'])
results=[];deadline=datetime.datetime(2026,10,15,5,46,tzinfo=datetime.timezone.utc).timestamp()
for i,name in enumerate(names,1):
 if time.time()>=deadline:print('PROBLEM: lane verification deadline reached',flush=True);break
 started=time.time();log=evidence/f'url-{i:02d}-{name}.log';xml=evidence/f'url-{i:02d}-{name}.xml';print(f'START {i}/13 {name}',flush=True)
 with log.open('w') as output:
  p=subprocess.Popen(['scripts/test.bash','--local','--test','tests/'+name+'.kts','--log',str(xml)],cwd=repo,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  (evidence/'url-child.json').write_text(json.dumps(dict(pid=p.pid,index=i,name=name)))
  try:p.wait(timeout=min(600,deadline-time.time()))
  except subprocess.TimeoutExpired:
   print('PROBLEM: outer command deadline reached; existing test bounds unchanged',file=output,flush=True);os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 executed=[]
 if xml.exists():
  executed=[dict(t.attrib) for t in ET.parse(xml).getroot().findall('test')]
 gate_ok=p.returncode==0 and len(executed)==1 and executed[0].get('name')=='foundation.url.protocol.'+name and executed[0].get('success')=='true'
 result=dict(index=i,name=name,exit_code=p.returncode,gate_ok=gate_ok,executed=executed,seconds=round(time.time()-started,3),log=str(log),xml=str(xml));results.append(result)
 (evidence/'url-verification-results.json').write_text(json.dumps(results,indent=2)+'\n');print('RESULT '+json.dumps(result),flush=True)
 findings=lane.parent.parent/'out/r146-findings.md'
 with findings.open('a') as out:out.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+' — OBSERVED: Consumer command result '+json.dumps(result)+'. INFER: '+('Invocation passed; remaining prescribed invocations still pending.' if gate_ok else 'Invocation failed; full output/XML retained and prescribed gate stopped without retry.')+'\n')
 if not gate_ok:print('PROBLEM: gate stopped on nonzero invocation; no retry',flush=True);break
print('TOTAL '+json.dumps(dict(invocations=len(results),passed=sum(x['gate_ok'] for x in results),failed=sum(not x['gate_ok'] for x in results))),flush=True)
