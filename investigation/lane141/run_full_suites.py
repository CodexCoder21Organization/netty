from pathlib import Path
import subprocess,os,time,json,signal,datetime,shutil,xml.etree.ElementTree as ET
lane=Path(__file__).resolve().parent.parent;repo=lane/'workspace/netty';evidence=lane/'evidence'
env=os.environ.copy();env.update(JAVA_HOME='/usr/lib/jvm/temurin-21-jdk-amd64',MAVEN_OPTS='-Xmx2g',MAVEN_USER_HOME=str(lane/'.m2'),JAVA_TOOL_OPTIONS='-Xmx2g')
results=[];deadline=datetime.datetime(2026,10,15,3,58,tzinfo=datetime.timezone.utc).timestamp()
for module in ['common','transport']:
 if time.time()>=deadline:print('PROBLEM: lane full-suite deadline reached',flush=True);break
 command=['./mvnw','-e','-B','-pl',module,'-Dmaven.repo.local='+str(lane/'.m2'),'-Dcheckstyle.skip','-Dforbiddenapis.skip','-Dxml.skip','-Dnohttp.skip','test']
 reports=repo/module/'target/surefire-reports'
 if reports.exists():shutil.rmtree(reports)
 started=time.time();log=evidence/('full-'+module+'.log');print('START full '+module,flush=True)
 with log.open('w') as output:
  p=subprocess.Popen(command,cwd=repo,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  try:p.wait(timeout=min(1200,deadline-time.time()))
  except subprocess.TimeoutExpired:
   print('PROBLEM: outer suite command deadline reached; existing test bounds unchanged',file=output,flush=True)
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 reports=repo/module/'target/surefire-reports';totals={k:0 for k in ['tests','failures','errors','skipped']}
 for f in reports.glob('TEST-*.xml'):
  root=ET.parse(f).getroot()
  for k in totals:totals[k]+=int(root.get(k,'0'))
 result=dict(module=module,exit_code=p.returncode,seconds=round(time.time()-started,3),**totals);results.append(result)
 (evidence/'full-suite-results.json').write_text(json.dumps(results,indent=2)+'\n');print('RESULT '+json.dumps(result),flush=True)
 dst=evidence/('full-'+module+'-reports');dst.mkdir(exist_ok=True)
 import shutil
 for f in reports.glob('*'):
  if f.is_file():shutil.copy2(f,dst/f.name)
 findings=lane.parent.parent/'out/r141-findings.md'
 with findings.open('a') as out:out.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+' — OBSERVED: Full custom-version suite '+json.dumps(result)+'. Reports copied under lane141/evidence/full-'+module+'-reports. INFER: '+('Suite passed; existing skips must be accounted for separately.' if p.returncode==0 else 'Suite did not pass; full logs/reports preserved, no green-suite claim.')+'\n')
