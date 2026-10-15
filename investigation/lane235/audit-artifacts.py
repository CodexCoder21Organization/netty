from pathlib import Path
import json,hashlib,zipfile,xml.etree.ElementTree as ET,subprocess
lane=Path(__file__).resolve().parent;stage=lane/'staged-artifacts';version='4.2.10.2-codexcoder21';ns={'m':'http://maven.apache.org/POM/4.0.0'}
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=lane/'netty',text=True).strip()
order=json.loads((stage/'CUSTOM-DEPENDENCIES.json').read_text())['publish_order'];assert len(order)==46
expected=['netty-parent', 'netty-bom', 'netty-dev-tools', 'netty-jfr-stub', 'netty-varhandle-stub', 'netty-common', 'netty-buffer', 'netty-pkitesting', 'netty-resolver', 'netty-testsuite-common', 'netty-transport', 'netty-codec-base', 'netty-transport-native-unix-common', 'netty-transport-rxtx', 'netty-transport-udt', 'netty-codec-compression', 'netty-codec-dns', 'netty-codec-haproxy', 'netty-codec-marshalling', 'netty-codec-memcache', 'netty-codec-mqtt', 'netty-codec-protobuf', 'netty-codec-redis', 'netty-codec-smtp', 'netty-codec-socks', 'netty-codec-stomp', 'netty-codec-xml', 'netty-handler', 'netty-transport-classes-epoll', 'netty-transport-classes-io_uring', 'netty-transport-classes-kqueue', 'netty-transport-native-unix-common-tests', 'netty-codec', 'netty-codec-classes-quic', 'netty-codec-http', 'netty-resolver-dns', 'netty-transport-native-epoll', 'netty-codec-http2', 'netty-codec-native-quic', 'netty-handler-proxy', 'netty-handler-ssl-ocsp', 'netty-resolver-dns-classes-macos', 'netty-transport-sctp', 'netty-codec-http3', 'netty-testsuite', 'netty-all']
assert set(order)==set(expected),(set(order)-set(expected),set(expected)-set(order))
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
