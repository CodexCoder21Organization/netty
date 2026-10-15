import subprocess,json,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parent/'netty'
def git(*args):return subprocess.check_output(['git',*args],cwd=repo,text=True)
prior='a66b8e41266dd9a8ae193cf3dea021b3b5547d7f';fix='7a9caa8cfd38683230db50ae83c58f22002044ba';path='transport/src/main/java/io/netty/channel/SingleThreadIoEventLoop.java';test='transport/src/test/java/io/netty/channel/nio/NioShutdownReentryTest.java'
version_files=git('diff-tree','--no-commit-id','--name-only','-r',prior).splitlines()
changes=git('diff','--name-only',prior,'HEAD').splitlines()
assert sorted(changes)==sorted(version_files+[path,test])
for p in version_files:
 assert git('show','HEAD:'+p)==git('show',prior+':'+p).replace('4.2.10.1-codexcoder21','4.2.10.2-codexcoder21'),p
assert git('show','HEAD:'+test)==git('show',fix+':'+test)
def edits(diff):return [l for l in diff.splitlines() if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
assert edits(git('diff',prior,'HEAD','--',path))==edits(git('diff','d7b4547b',fix,'--',path))
assert not git('status','--porcelain')
print(json.dumps(dict(prior=prior,fix=fix,head=git('rev-parse','HEAD').strip(),maintenance_base=git('rev-parse','origin/maint/4.2.10-codexcoder21').strip(),version_files=version_files,version_locations=63,pom_count=62,production_edits_equal_fix=True,test_equal_fix=True,source_changes=changes),indent=2))
