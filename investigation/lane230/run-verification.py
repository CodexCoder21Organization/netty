from pathlib import Path
import subprocess,sys,datetime,json
lane=Path(__file__).resolve().parent
findings=lane.parent.parent/'out/r230-findings.md'
stages=[('full-common',600,['-pl','common','test']),('full-transport',600,['-pl','transport','test']),('bom-install',300,['-f','bom/pom.xml','-DskipTests','install']),('full-published-reactor',2700,['-pl','common,buffer,transport,handler,codec,all','-am','-DskipTests','install'])]
for label,budget,args in stages:
 for cmd in [['git','fetch','origin'],['git','rebase','origin/maint/4.2.10-codexcoder21']]:subprocess.run(cmd,cwd=lane/'netty',check=True,timeout=120)
 available=int(datetime.datetime(2026,10,15,14,3,tzinfo=datetime.timezone.utc).timestamp()-datetime.datetime.now(datetime.timezone.utc).timestamp())
 if available<=0:raise SystemExit('Lane work deadline reached')
 r=subprocess.run([sys.executable,str(lane/'run-maven.py'),label,str(min(budget,available))]+args,cwd=lane)
 subprocess.run([sys.executable,str(lane/'summarize-tests.py'),str(lane/'evidence'/label)],check=True)
 data=json.loads((lane/'evidence'/label/'result.json').read_text());counts=json.loads((lane/'evidence'/label/'test-counts.json').read_text())
 with findings.open('a') as f:
  f.write('\n## '+datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')+' — '+label+'\nOBSERVED: '+json.dumps(data)+'\nTest totals: '+json.dumps([{k:v for k,v in c.items() if k!='suites'} for c in counts])+'\n')
 if r.returncode:raise SystemExit(r.returncode)
