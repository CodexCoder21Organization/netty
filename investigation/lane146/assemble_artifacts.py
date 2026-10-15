from pathlib import Path
import xml.etree.ElementTree as ET,hashlib,shutil,json,sys,re
lane=Path(__file__).resolve().parent.parent
repo=lane/'.m2/io/netty';version='4.2.10.1-codexcoder21'
dest=lane.parent.parent/'publish/netty-codexcoder21-2'
ns={'m':'http://maven.apache.org/POM/4.0.0'}
models={}
def value(node,path,default=''):
 x=node.find(path,ns);return x.text.strip() if x is not None and x.text else default
for p in repo.glob('*/'+version+'/*.pom'):
 root=ET.parse(p).getroot();aid=value(root,'m:artifactId');assert aid==p.parent.parent.name
 models[aid]=(p,root)
assert 'netty-all' in models and 'netty-bom' in models and 'netty-parent' in models
edges={a:set() for a in models};refs=[]
for a,(p,root) in models.items():
 props={'project.version':version,'project.groupId':'io.netty','pom.version':version,'os.detected.classifier':'linux-x86_64','os.detected.arch':'x86_64'}
 for model in [models['netty-parent'][1],root]:
  node=model.find('m:properties',ns)
  if node is not None:
   for child in node:props[child.tag.split('}',1)[-1]]=child.text.strip() if child.text else ''
 def expand(s):
  for _ in range(20):
   t=re.sub(r'\$\{([^}]+)\}',lambda m:props.get(m.group(1),m.group()),s)
   if t==s:return t
   s=t
  raise AssertionError(('property expansion did not converge',a,s))
 management={}
 for model in [models['netty-parent'][1],models['netty-bom'][1],root]:
  for d in model.findall('m:dependencyManagement/m:dependencies/m:dependency',ns):
   management[(expand(value(d,'m:groupId')),expand(value(d,'m:artifactId')))]=expand(value(d,'m:version'))

 parent=root.find('m:parent',ns)
 if parent is not None and value(parent,'m:groupId')=='io.netty' and expand(value(parent,'m:version'))==version:edges[a].add(value(parent,'m:artifactId'))
 deps=root.findall('m:dependencies/m:dependency',ns)+root.findall('m:dependencyManagement/m:dependencies/m:dependency',ns)
 for d in deps:
  group=expand(value(d,'m:groupId'));dv=expand(value(d,'m:version'));scope=value(d,'m:scope','compile');typ=value(d,'m:type','jar');artifact=value(d,'m:artifactId');classifier=value(d,'m:classifier')
  if group!='io.netty':continue
  artifact=expand(artifact);classifier=expand(classifier)
  if not dv:dv=management.get((group,artifact),'')
  assert dv and '${' not in dv,(a,artifact,'unresolved managed version',dv)
  refs.append(dict(owner=a,artifact=artifact,version=dv,scope=scope,type=typ,classifier=classifier))
  managed=d in root.findall('m:dependencyManagement/m:dependencies/m:dependency',ns)
  # Managed entries only require a POM when imported. Runtime dependencies can inherit their version.
  if scope=='test' or (managed and scope!='import'):continue
  if dv!=version:continue
  assert artifact in models,(a,artifact,'missing custom module')
  edges[a].add(artifact)
  if typ=='jar' and classifier:
   assert (repo/artifact/version/(artifact+'-'+version+'-'+classifier+'.jar')).exists(),(a,artifact,classifier,'missing classifier')
# Parent/BOM first; all last. Include build helpers so their installed POM references are also usable.
order=[];pending=set(models)
while pending:
 ready=sorted(a for a in pending if not (edges[a]&pending))
 assert ready,('dependency cycle',pending)
 ready.sort(key=lambda a:(a!='netty-parent',a!='netty-bom',a=='netty-all',a))
 for a in ready:order.append(a);pending.remove(a)
order.remove('netty-all');order.append('netty-all')
if dest.exists():shutil.rmtree(dest)
dest.mkdir(parents=True)
manifest=[f'Version: {version}','One --artifact-dir invocation per directory below. No files were published.','Built POM dependency audit: CUSTOM-DEPENDENCIES.json','Publish order (parents/BOMs, then dependencies, then netty-all):']
for i,a in enumerate(order,1):
 p,root=models[a];out=dest/a;out.mkdir()
 files=[p]+[f for f in p.parent.glob('*.jar') if not any(f.name.endswith(x) for x in ['-tests.jar','-test-sources.jar','-javadoc.jar'])]
 if value(root,'m:packaging','jar')!='pom':assert any(f.name==a+'-'+version+'.jar' for f in files),(a,'missing main jar')
 for f in files:
  target=out/f.name;shutil.copy2(f,target)
  data=target.read_bytes()
  for algorithm in ['sha1','sha256']:(out/(f.name+'.'+algorithm)).write_text(hashlib.new(algorithm,data).hexdigest()+'\n')
 assert len(list(out.glob('*.pom')))==1
 manifest.append(f'{i:02d}. {a}  io.netty:{a}:{version}  files={len(files)}')
(dest/'MANIFEST.txt').write_text('\n'.join(manifest)+'\n')
(dest/'CUSTOM-DEPENDENCIES.json').write_text(json.dumps(dict(version=version,publish_order=order,dependencies=refs),indent=2)+'\n')
print(dest);print('directories',len(order));print('\n'.join(manifest))
