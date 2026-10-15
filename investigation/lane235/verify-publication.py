from pathlib import Path
import urllib.request,urllib.error,hashlib,json,concurrent.futures,zipfile,io,subprocess,datetime
lane=Path(__file__).resolve().parent
stage=lane/'staged-artifacts';audit=json.loads((lane/'evidence/artifact-audit.json').read_text());head=audit['head'];v=audit['version']
files=[(a.name,f) for a in stage.iterdir() if a.is_dir() for f in a.iterdir()]
def verify(item):
 a,f=item;u=f'https://kotlin.directory/io/netty/{a}/{v}/{f.name}';r=dict(artifact=a,file=f.name,url=u)
 try:
  with urllib.request.urlopen(u,timeout=60) as response:data=response.read();r['status']=response.status
  r['sha256']=hashlib.sha256(data).hexdigest();r['matches_staged']=data==f.read_bytes()
  if f.name==f'{a}-{v}.jar':
   with zipfile.ZipFile(io.BytesIO(data)) as z:meta=z.read('META-INF/io.netty.versions.properties').decode()
   r['metadata_matches']=all(s in meta for s in [a+'.version='+v,a+'.longCommitHash='+head,a+'.repoStatus=clean'])
   if a=='netty-transport':
    (stage/'downloaded-netty-transport.jar').write_bytes(data)
    (lane/'evidence/downloaded-transport-metadata.properties').write_text(meta)
 except urllib.error.HTTPError as e:r['status']=e.code;r['error']=str(e)
 except Exception as e:r['error']=repr(e)
 return r
results=list(concurrent.futures.ThreadPoolExecutor(6).map(verify,files))
(lane/'evidence/publication-probes.json').write_text(json.dumps(results,indent=2)+'\n')
fail=[r for r in results if r.get('status')!=200 or not r.get('matches_staged') or r.get('metadata_matches') is False]
summary=dict(head=head,version=v,probes=len(results),http200=sum(r.get('status')==200 for r in results),matching=sum(r.get('matches_staged',False) for r in results),main_metadata_verified=sum(r.get('metadata_matches',False) for r in results),failures=fail,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(lane/'evidence/verification-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
assert len(files)==408,(len(files),'expected 136 payloads plus 272 checksums')
assert not fail,fail
