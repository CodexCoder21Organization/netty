import subprocess,os,signal,sys,time,json,shutil
from pathlib import Path
lane=Path(__file__).resolve().parent;repo=lane/'netty';label=sys.argv[1];budget=int(sys.argv[2]);args=sys.argv[3:]
env=os.environ.copy();env.update(JAVA_HOME='/usr/lib/jvm/temurin-21-jdk-amd64',JAVA_OPTS='-Xmx2g',MAVEN_OPTS='-Xmx2g',JAVA_TOOL_OPTIONS='-Xmx2g',PATH='/usr/lib/jvm/temurin-21-jdk-amd64/bin:'+env['PATH'])
env.update(LD_LIBRARY_PATH=str(lane/'toolchain/root/usr/lib/x86_64-linux-gnu'),RUSTUP_HOME=str(lane/'toolchain/rustup'),CARGO_HOME=str(lane/'toolchain/cargo'),CARGO_BUILD_JOBS='1',CMAKE_BUILD_PARALLEL_LEVEL='1',M4=str(lane/'toolchain/root/usr/bin/m4'),AUTOM4TE=str(lane/'toolchain/root/usr/bin/autom4te'))
env['PATH']=':'.join(str(lane/p) for p in ['toolchain/bin','toolchain/root/usr/bin','toolchain/go/bin','toolchain/cargo/bin'])+':'+env['PATH']
env.update({k:str(lane/'toolchain/root/usr/bin'/v) for k,v in {'AUTOCONF':'autoconf','AUTOHEADER':'autoheader','AUTOMAKE':'automake-1.16','ACLOCAL':'aclocal-1.16'}.items()})
cmd=['./mvnw','-e','-B','-Dmaven.repo.local='+str(lane/'m2')]+args
out=lane/'evidence'/label;out.mkdir(exist_ok=True)
for p in repo.glob('*/target/surefire-reports'):
 shutil.rmtree(p)
start=time.time()
with (out/'maven.log').open('w') as f:
 p=subprocess.Popen(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 (lane/'evidence/active-child.json').write_text(json.dumps(dict(pid=p.pid,label=label,command=cmd)))
 try:rc=p.wait(timeout=budget)
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGTERM)
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  rc=124
for d in repo.glob('*/target/surefire-reports'):
 shutil.copytree(d,out/d.parent.parent.name)
result=dict(label=label,command=cmd,exit_code=rc,elapsed_seconds=time.time()-start,head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);sys.exit(rc)
