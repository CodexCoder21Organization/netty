from pathlib import Path
import subprocess,json
lane=Path(__file__).resolve().parent
result=json.loads((lane/'evidence/final-pre-pr-tests/result.json').read_text());assert result['exit_code']==0
counts=json.loads((lane/'evidence/final-pre-pr-tests/test-counts.json').read_text());by={r['module']:r for r in counts}
assert set(by)=={'common','transport'}
for module,tests,skipped in [('common',1430,7),('transport',391,9)]:
 r=by[module];assert (r['tests'],r['failures'],r['errors'],r['skipped'])==(tests,0,0,skipped),r
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=lane/'netty',text=True).strip();assert head==result['head']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=lane/'netty',text=True)
remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/release/4.2.10.2-codexcoder21'],cwd=lane/'netty',text=True).split()[0];assert remote==head
assert json.loads((lane/'evidence/full-published-reactor/result.json').read_text())['exit_code']==0
assert json.loads((lane/'evidence/artifact-audit.json').read_text())['head']==head
body=(lane/'evidence/pr-body-template.md').read_text().replace('@HEAD@',head).replace('@TRANSPORT@','391').replace('@TRANSPORT_SKIPS@','9').replace('@BUILD_RESULT@','Complete 45-module publication reactor (`common,buffer,transport,handler,codec,all -am -DskipTests install`) and independent BOM install both exit 0. Staging/audit covers exactly the prior 46 artifact names: 136 POM/JAR payloads, 272 matching checksums, and all 44 main jars record this clean commit and version. Linux native epoll and QUIC classifier builds succeed. The final common/transport gate after the last maintenance rebase also exits 0 with 1,821 tests, zero failures/errors and 16 existing skips. Native module test suites and non-Linux classifier builds were not run.')
assert '@HEAD@' not in body and '@BUILD_RESULT@' not in body
(lane/'evidence/pr-body.md').write_text(body)
existing=json.loads(subprocess.check_output(['gh','api','repos/CodexCoder21Organization/netty/pulls?state=all&head=CodexCoder21Organization:release/4.2.10.2-codexcoder21'],text=True));assert not existing,[(p['html_url'],p['state']) for p in existing]
request=dict(title='Release 4.2.10.2-codexcoder21 with final channel cleanup',head='release/4.2.10.2-codexcoder21',base='maint/4.2.10-codexcoder21',body=body,draft=False)
p=lane/'evidence/pr-request.json';p.write_text(json.dumps(request))
response=json.loads(subprocess.check_output(['gh','api','-X','POST','repos/CodexCoder21Organization/netty/pulls','--input',str(p)],text=True))
assert response['state']=='open' and response['draft'] is False and response['head']['sha']==head and response['base']['ref']==request['base']
summary={k:response[k] for k in ['html_url','number','state','draft','mergeable','mergeable_state','created_at']};summary['head']=head;summary['base']=response['base']['ref']
(lane/'evidence/pr-created.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
