from pathlib import Path
import subprocess,shutil,sys
lane=Path(__file__).resolve().parent;dest=lane/'evidence-checkout/investigation/lane235'
exclude={'philosophy.md','testing.md','code-review.md','flaky-skill-read.txt','urlprotocol-build.kts','urlprotocol-readme-read.txt','urlprotocol-tree.json','lane230-files.json','artifact-audit.json'}
for f in (lane/'evidence').rglob('*'):
 if f.is_file() and f.name not in exclude and f.suffix not in {'.jar','.deb','.gz'}:
  out=dest/f.relative_to(lane/'evidence');out.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(f,out)
for n in ['assemble-artifacts.py','audit-artifacts.py','run-maven.py','publish-artifacts.py','verify-publication.py','checkpoint-evidence.py']:
 shutil.copy2(lane/n,dest/n)
# Current audit is distinguished from the previously downloaded prior-lane audit.
if (lane/'evidence/current-artifact-audit.json').exists():shutil.copy2(lane/'evidence/current-artifact-audit.json',dest/'artifact-audit.json')
shutil.copy2(lane.parent.parent/'out/r235-findings.md',dest/'FINDINGS.md')
subprocess.run(['git','add','.'],cwd=lane/'evidence-checkout',check=True)
r=subprocess.run(['git','diff','--cached','--quiet'],cwd=lane/'evidence-checkout')
if r.returncode:
 subprocess.run(['git','commit','-m',sys.argv[1],'-m','Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>'],cwd=lane/'evidence-checkout',check=True)
 subprocess.run(['git','push','origin','HEAD'],cwd=lane/'evidence-checkout',check=True,timeout=60)
