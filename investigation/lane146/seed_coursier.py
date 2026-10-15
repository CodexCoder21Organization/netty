from pathlib import Path
import hashlib,shutil,json
lane=Path(__file__).resolve().parent.parent;version='4.2.10.1-codexcoder21';stage=lane.parent.parent/'publish/netty-codexcoder21-2'
roots=['https/kotlin.directory','https/repo1.maven.org/maven2','https/repo.maven.apache.org/maven2','https/maven-central.storage-download.googleapis.com/maven2']
count=0
for module in stage.iterdir():
 if not module.is_dir():continue
 for f in module.iterdir():
  if not f.is_file():continue
  assert version in f.name,f
  for root in roots:
   dest=lane/'coursier-cache'/root/'io/netty'/module.name/version/f.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
   dest.with_name('.'+dest.name+'.checked').touch()
   if f.suffix in ['.jar','.pom']:dest.with_name('.'+dest.name+'__sha1.computed').write_bytes(hashlib.sha1(f.read_bytes()).digest())
   for suffix in ['.error','.not-found','.part']:
    dest.with_name('.'+dest.name+suffix).unlink(missing_ok=True)
   count+=1
print(json.dumps({'version':version,'roots':roots,'copied_files':count}))
