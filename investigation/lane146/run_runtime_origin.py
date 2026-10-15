from pathlib import Path
import subprocess,os,time,json,datetime,signal,hashlib,xml.etree.ElementTree as ET,shutil
lane=Path(__file__).resolve().parent.parent;evidence=lane/'evidence';version='4.2.10.1-codexcoder21';stage=lane.parent.parent/'publish/netty-codexcoder21-2';verify=lane/'workspace/UrlProtocol-verification'
audit=json.loads((evidence/'artifact-audit.json').read_text());modules=[p for p in stage.iterdir() if p.is_dir()];files=audit['files'];checksums=audit['checksums']
cp=(evidence/'kompile-classpath.txt').read_text().strip();env=os.environ.copy();env.update(JAVA_HOME='/usr/lib/jvm/temurin-21-jdk-amd64',COURSIER_CACHE=str(lane/'coursier-cache'),COURSIER_ARCHIVE_CACHE=str(lane/'coursier-archives'),COURSIER_JVM_CACHE=str(lane/'coursier-jvm'),JAVA_TOOL_OPTIONS='-Xmx2g',PATH='/usr/lib/jvm/temurin-21-jdk-amd64/bin:'+env['PATH'])
with (evidence/'required-build-pins-fetch.log').open('w') as out:subprocess.run(['java','-cp',str(evidence)+':'+cp,'RequiredBuildPinsProbe',version],cwd=lane,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=300,check=True)
# The classpath is the lane-private runner's unaltered kompile dependency classpath.
p=verify/'tests/diagnoseLane146NettyBinding.kts';shutil.copy2(evidence/p.name,p)
xml=evidence/'runtime-binding-origin.xml';log=evidence/'runtime-binding-origin.log';started=time.time()
try:
 with log.open('w') as out:
  proc=subprocess.Popen(['scripts/test.bash','--local','--test','tests/'+p.name,'--log',str(xml)],cwd=verify,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
  (evidence/'diagnostic-child.json').write_text(json.dumps({'pid':proc.pid}))
  try:proc.wait(timeout=600)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   raise
finally:p.unlink(missing_ok=True)
executed=[dict(t.attrib) for t in ET.parse(xml).getroot().findall('test')] if xml.exists() else []
passed=proc.returncode==0 and len(executed)==1 and executed[0].get('name')=='foundation.url.protocol.diagnoseLane146NettyBinding' and executed[0].get('success')=='true'
result=dict(pid=proc.pid,exit_code=proc.returncode,seconds=round(time.time()-started,3),passed=passed,executed=executed)
(evidence/'runtime-origin-result.json').write_text(json.dumps(result,indent=2)+'\n');print('ORIGIN_RESULT',json.dumps(result),flush=True)
with (lane.parent.parent/'out/r146-findings.md').open('a') as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+' — OBSERVED: Rebuilt artifact audit '+json.dumps(dict(directories=len(modules),files=files,checksums=checksums))+'; exact Fetch using rebuilt jars passed. Runtime-origin diagnostic '+json.dumps(result)+'. INFER: '+('Custom transport/buffer/common origins proven; prescribed consumer gate may now begin.' if passed else 'Origin gate did not pass; prescribed tests remain unrun and publication held.')+'\n')
assert passed,'Runtime-origin gate failed; no consumer test may run'
print('READY_FOR_13_INVOCATIONS',flush=True)
