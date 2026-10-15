from pathlib import Path
import json,subprocess,datetime
lane=Path(__file__).resolve().parent.parent;ev=lane/'evidence';summary=json.loads((ev/'gate-summary.json').read_text());audit=json.loads((ev/'artifact-audit.json').read_text());results=json.loads((ev/'url-verification-results.json').read_text())
assert len(results)==13 and summary['status']=='PUBLISH-READY'
netty_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=lane/'workspace/netty',text=True).strip();url_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=lane/'workspace/UrlProtocol',text=True).strip()
body=(ev/'pr-body-draft.md').read_text()
build=f'''The complete 45-module reactor was rebuilt serially with the lane-private toolchain and `-DskipTests`, plus the independent BOM. Build exit: 0. Staging at `/tmp/claude-1000/-code/e2107bbc-8389-42b8-8447-42cf956a6745/scratchpad/publish/netty-codexcoder21-2/` contains {audit['directories']} one-POM directories, {audit['files']} POM/JAR files, and {audit['checksums']} independently verified SHA1/SHA256 checksums. MANIFEST.txt gives parent/BOM-first dependency order and netty-all last. STATUS.txt is **PUBLISH-READY**. All 31 recorded upstream-coordinate cache JAR hashes remain unchanged.

The exact runner API selects all five existing production pins at the custom version. Some unpinned, unchanged modules such as HTTP remain upstream; codec does not depend on HTTP, and HTTP has no fork implementation change. An extra assertion that every module must switch was refuted and preserved in the evidence, rather than adding more pins. The rebuilt transport bytecode has `confirmShutdown()`, and the separate runtime diagnostic passed assertions on actual transport/buffer/common class-source paths at the custom version before the consumer gate began.

Release source: https://github.com/CodexCoder21Organization/netty/commit/{netty_head}
Pin source: https://github.com/CodexCoder21Organization/UrlProtocol/commit/{url_head}'''
rows=['Consumer gate: **13/13 PASS**, no retries. Every command reported exactly one matching successful test in XML. The racing case retained 50 iterations in each of its ten serial invocations; both connection tests retained their existing 2000 ms budgets.','', '| Invocation | Scenario | Result | Function time |','| --- | --- | --- | --- |']
for x in results:
 scenario='Deterministic shutdown' if x['index']==1 else 'Racing shutdown '+str(x['index']-1)+'/10' if x['index']<=11 else 'Graceful close event' if x['index']==12 else 'Connection listener isolation'
 rows.append(f"| {x['index']} | {scenario} | PASS | {int(x['executed'][0]['time'])/1000:.3f} s |")
body=body.replace('REBUILD_AND_ARTIFACT_RESULTS',build).replace('CONSUMER_GATE_RESULTS','\n'.join(rows))
(ev/'pr-body.md').write_text(body)
state=json.loads(subprocess.check_output(['gh','api','repos/CodexCoder21Organization/netty/pulls/2'],text=True));assert state['state']=='open' and state['draft'] and state['head']['sha']==netty_head,state['state']
payload=dict(title='Build 4.2.10.1-codexcoder21 with shutdown and allocator fixes',body=body);(ev/'pr-update.json').write_text(json.dumps(payload,ensure_ascii=False))
response=subprocess.check_output(['gh','api','--method','PATCH','repos/CodexCoder21Organization/netty/pulls/2','--input',str(ev/'pr-update.json')],text=True);(ev/'updated-pr.json').write_text(response);updated=json.loads(response)
assert updated['body']==body and updated['draft'] and updated['state']=='open'
print(json.dumps({k:updated[k] for k in ['html_url','state','draft','title']},ensure_ascii=False))
