from pathlib import Path
import subprocess,os
lane=Path('.').resolve();cp=(lane/'evidence/kompile-classpath.txt').read_text().strip();old='4.2.10.Final-codexcoder21-1';new='4.2.10.1-codexcoder21'
fixture=lane/'evidence/ordering-pom-fixture'
for p in (lane/'.m2/io/netty').glob('*/'+old+'/*.pom'):
 out=fixture/'io/netty'/p.parent.parent.name/new/p.name.replace(old,new);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(p.read_text().replace(old,new))
(fixture/'README.txt').write_text('Resolution-only POM fixture, no JARs. Version text changed from lane141 POMs solely to prove mediation before rebuild. Not a publishable artifact.\n')
subprocess.run(['javac','-proc:none','-cp',cp,'evidence/CandidateFetchProbe.java'],check=True)
env=os.environ.copy();env['COURSIER_CACHE']=str(lane/'coursier-cache')
for version,label in [(old,'original-fail-first'),(new,'candidate-pass')]:
 with open(lane/f'evidence/{label}.log','w') as out:
  r=subprocess.run(['java','-cp','evidence:'+cp,'CandidateFetchProbe',version,fixture.as_uri(),'pom-only'],env=env,stdout=out,stderr=subprocess.STDOUT)
 print(label,r.returncode,flush=True)
with open('evidence/native-candidate-tree.log','w') as out:
 r=subprocess.run(['/home/u/bin/cs','resolve','--tree','--repository',fixture.as_uri(),'io.netty:netty-transport:'+new,'io.netty:netty-transport:4.2.10.Final'],env=env,stdout=out,stderr=subprocess.STDOUT)
print('native candidate',r.returncode,flush=True)
with open('evidence/consumer-original-full-tree.log','w') as out:
 r=subprocess.run(['/home/u/bin/cs','resolve','--tree','--repository','https://kotlin.directory','--repository',(lane/'.m2').as_uri(),'community.kotlin.libp2p:jvm-libp2p:1.3.0-codexcoder21-snapshot-25','io.netty:netty-transport:'+old],env=env,stdout=out,stderr=subprocess.STDOUT)
print('full consumer tree',r.returncode,flush=True)
