from pathlib import Path
import json,hashlib,zipfile,xml.etree.ElementTree as ET,subprocess
lane=Path(__file__).resolve().parent;stage=lane/'staged-artifacts';version='4.2.10.2-codexcoder21';ns={'m':'http://maven.apache.org/POM/4.0.0'}
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=lane/'netty',text=True).strip()
order=json.loads((stage/'CUSTOM-DEPENDENCIES.json').read_text())['publish_order'];assert len(order)==46
payloads=[];main=[]
for a in order:
 d=stage/a;poms=list(d.glob('*.pom'));assert len(poms)==1
 model=ET.parse(poms[0]).getroot();v=model.find('m:version',ns)
 if v is None:v=model.find('m:parent/m:version',ns)
 assert v.text==version,(a,v.text)
 for f in sorted(d.iterdir()):
  if f.suffix not in ['.pom','.jar']:continue
  for algorithm in ['sha1','sha256']:assert (d/(f.name+'.'+algorithm)).read_text().strip()==hashlib.new(algorithm,f.read_bytes()).hexdigest()
  payloads.append(dict(module=a,file=f.name,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
 jar=d/(a+'-'+version+'.jar')
 if jar.exists():
  with zipfile.ZipFile(jar) as z:
   metadata=z.read('META-INF/io.netty.versions.properties').decode()
   assert a+'.version='+version in metadata,(a,'version',metadata)
   assert a+'.longCommitHash='+head in metadata,(a,'head',metadata)
   assert a+'.repoStatus=clean' in metadata,(a,'status',metadata)
  main.append(a)
assert len(payloads)==136,len(payloads)
assert len(main)==44,len(main)
source=stage/'netty-transport'/('netty-transport-'+version+'-sources.jar')
with zipfile.ZipFile(source) as z:
 assert z.read('io/netty/channel/SingleThreadIoEventLoop.java')==(lane/'netty/transport/src/main/java/io/netty/channel/SingleThreadIoEventLoop.java').read_bytes()
result=dict(head=head,version=version,module_directories=len(order),payloads=len(payloads),verified_checksum_files=2*len(payloads),main_jars=len(main),source_jar_matches=True,files=payloads)
(lane/'evidence/artifact-audit.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='files'})
