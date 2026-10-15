from pathlib import Path
import subprocess,os,signal,json,time,shutil,xml.etree.ElementTree as ET
lane=Path(__file__).resolve().parent.parent;repo=lane/'netty-2';evidence=lane/'evidence';env=os.environ.copy();env.update(MAVEN_OPTS='-Xmx2g',JAVA_TOOL_OPTIONS='-Xmx2g')
base=['./mvnw','-B','-Dmaven.repo.local='+str(lane/'m2'),'-Dcheckstyle.skip','-Dforbiddenapis.skip','-Dxml.skip','-Dnohttp.skip']
for stage,args,seconds in [('install-test-dependencies',['-pl','transport','-am','-DskipTests','install'],600),('full-transport',['-pl','transport','test'],900)]:
 for gitcmd in [['git','fetch','origin'],['git','rebase','origin/4.2']]:subprocess.run(gitcmd,cwd=repo,check=True,timeout=120)
 if stage=='full-transport':
  reports=repo/'transport/target/surefire-reports'
  if reports.exists():shutil.rmtree(reports)
 started=time.monotonic()
 with (evidence/('netty2-'+stage+'.log')).open('w') as output:
  p=subprocess.Popen(base+args,cwd=repo,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  try:p.wait(timeout=seconds)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 print(stage,'exit',p.returncode,'seconds',round(time.monotonic()-started,2),flush=True)
 if p.returncode:raise SystemExit(p.returncode)
 if stage=='full-transport':
  totals={k:0 for k in ['tests','failures','errors','skipped']}
  target=evidence/'netty2-full-transport-reports';target.mkdir(exist_ok=True)
  for f in reports.glob('*'):
   if f.is_file():shutil.copy2(f,target/f.name)
  for f in reports.glob('TEST-*.xml'):
   root=ET.parse(f).getroot()
   for k in totals:totals[k]+=int(root.get(k,'0'))
  totals.update(label='development transport',exit_code=p.returncode)
  path=evidence/'module-results.json';results=json.loads(path.read_text());results.append(totals);path.write_text(json.dumps(results,indent=2)+'\n');print(totals,flush=True)
