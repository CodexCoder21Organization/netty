from pathlib import Path
import subprocess,os,json,time,datetime,signal,sys
lane=Path(__file__).resolve().parent
stage=lane/'staged-artifacts';ev=lane/'evidence/publication';ev.mkdir(exist_ok=True)
order=json.loads((stage/'CUSTOM-DEPENDENCIES.json').read_text())['publish_order']
assert len(order)==46
results=[]
deadline=datetime.datetime(2026,10,15,14,55,tzinfo=datetime.timezone.utc).timestamp()
env=dict(os.environ,JAVA_OPTS='-Xmx512m',JAVA_TOOL_OPTIONS='-Xmx512m')
for a in order:
 if time.time()>=deadline:raise SystemExit('Publication deadline reached')
 steer=lane.parent.parent/'out/r235-steer.md'
 if steer.exists():print('Steer file present; review before publication',flush=True);raise SystemExit(2)
 cmd=['/home/helena/bin/coursier','launch','community.kotlin.maven.artifact.publishing:community-kotlin-maven-artifact-publishing:0.0.6','-r','https://kotlin.directory','--','--artifact-dir',str(stage/a),'--api-url','https://api.kotlin.directory/upload','--force']
 start=time.time()
 with (ev/(a+'.log')).open('w') as f:
  p=subprocess.Popen(cmd,cwd=lane,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
  (ev/'active-child.json').write_text(json.dumps(dict(pid=p.pid,artifact=a)))
  try:rc=p.wait(timeout=min(180,max(1,deadline-time.time())))
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   rc=124
 result=dict(artifact=a,exit_code=rc,elapsed_seconds=time.time()-start,command=cmd,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 results.append(result);(ev/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(result),flush=True)
 with (lane.parent.parent/'out/r235-findings.md').open('a') as f:f.write('\nOBSERVED publication '+result['utc']+': io.netty:'+a+':4.2.10.2-codexcoder21 publisher exit '+str(rc)+'; output retained at publication/'+a+'.log.\n')
 if rc:raise SystemExit(rc)
print('All 46 publisher processes returned 0.',flush=True)
