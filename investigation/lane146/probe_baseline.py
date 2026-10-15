from pathlib import Path
import subprocess,os
cp=Path('../lane141/evidence/kompile-classpath.txt').read_text().strip()
p=Path('evidence/CoursierVersionProbe.java');p.write_text(Path('../lane141/evidence/CoursierVersionProbe.java').read_text())
subprocess.run(['javac','-cp',cp,str(p)],check=True)
env=os.environ.copy();env['COURSIER_CACHE']=str(Path('coursier-cache').resolve())
with open('evidence/baseline-exact-runner.log','w') as f:
 r=subprocess.run(['java','-cp','evidence:'+cp,'CoursierVersionProbe'],env=env,stdout=f,stderr=subprocess.STDOUT)
print('baseline exit',r.returncode)
