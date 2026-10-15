from pathlib import Path
import shutil,subprocess,sys
lane=Path(__file__).resolve().parent.parent;out=lane/'workspace/netty-evidence/investigation/lane146';out.mkdir(parents=True,exist_ok=True)
for p in (lane/'evidence').iterdir():
 if p.is_file() and p.suffix not in ['.class'] and p.name not in ['kompile-classpath.txt']:
  shutil.copy2(p,out/p.name)
shutil.copytree(lane/'evidence/ordering-pom-fixture',out/'ordering-pom-fixture',dirs_exist_ok=True)
shutil.copy2(lane.parent.parent/'out/r146-findings.md',out/'findings.md')
subprocess.run(['git','add','investigation/lane146'],cwd=out.parent.parent,check=True)
r=subprocess.run(['git','diff','--cached','--quiet'],cwd=out.parent.parent)
if r.returncode:
 subprocess.run(['git','commit','-m',sys.argv[1]+'\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>'],cwd=out.parent.parent,check=True)
 subprocess.run(['git','push','origin','evidence/lane146-version-selection'],cwd=out.parent.parent,check=True)
