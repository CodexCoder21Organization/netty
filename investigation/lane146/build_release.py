from pathlib import Path
import os,subprocess,json,datetime,signal,time
lane=Path(__file__).resolve().parent.parent;repo=lane/'workspace/netty';env=os.environ.copy()
env.update(JAVA_HOME='/usr/lib/jvm/temurin-21-jdk-amd64',MAVEN_OPTS='-Xmx2g',JAVA_TOOL_OPTIONS='-Xmx2g',MAVEN_USER_HOME=str(lane/'.m2'),PATH=str(lane/'toolchain/root/usr/bin')+':'+str(lane/'toolchain/go/bin')+':/usr/lib/jvm/temurin-21-jdk-amd64/bin:'+env['PATH'],LD_LIBRARY_PATH=str(lane/'toolchain/root/usr/lib/x86_64-linux-gnu'),RUSTUP_HOME=str(lane/'toolchain/rustup'),CARGO_HOME=str(lane/'toolchain/cargo'),CARGO_BUILD_JOBS='1',CMAKE_BUILD_PARALLEL_LEVEL='1')
base=['./mvnw','-e','-B','-Dmaven.repo.local='+str(lane/'.m2')]
def run(label,args):
 print('START',label,args,flush=True)
 with (lane/'evidence'/f'{label}.log').open('w') as out:
  p=subprocess.Popen(base+args,cwd=repo,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
  (lane/'evidence/build-child.json').write_text(json.dumps({'pid':p.pid,'label':label}))
  try:rc=p.wait(timeout=min(5400,datetime.datetime(2026,10,15,5,46,tzinfo=datetime.timezone.utc).timestamp()-time.time()))
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise
 print('RESULT',label,rc,flush=True)
 if rc:raise SystemExit(rc)
run('versions-set',['versions:set','-DnewVersion=4.2.10.1-codexcoder21','-DgenerateBackupPoms=false'])
p=repo/'bom/pom.xml';s=p.read_text();assert s.count('4.2.10.Final-codexcoder21-1')==1;p.write_text(s.replace('4.2.10.Final-codexcoder21-1','4.2.10.1-codexcoder21'))
p=repo/'README.md';p.write_text(p.read_text().replace('4.2.10.Final-codexcoder21-1','4.2.10.1-codexcoder21'))
assert not any('4.2.10.Final-codexcoder21-1' in p.read_text() for p in repo.rglob('pom.xml') if 'target' not in p.parts)
print('VERSION_EDIT_DONE',flush=True)
run('bom-install',['-f','bom/pom.xml','-DskipTests','install'])
run('custom-reactor-install',['-pl','common,buffer,transport,handler,codec,all','-am','-DskipTests','install'])
