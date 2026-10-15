from pathlib import Path
import os,signal,subprocess,time,json
lane=Path(__file__).resolve().parent.parent;ev=lane/'evidence'
# Exclude this cleanup call and the tool/agent processes that launched it.
ancestors=set();pid=os.getpid()
while pid>1 and pid not in ancestors:
 ancestors.add(pid)
 try:pid=int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[1])
 except (FileNotFoundError,ProcessLookupError):break

def owned():
 found=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit() or int(proc.name) in ancestors:continue
  try:
   cwd=(proc/'cwd').resolve();args=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  except (FileNotFoundError,PermissionError,ProcessLookupError):continue
  if cwd==lane or lane in cwd.parents:found.append((int(proc.name),args))
 return found
before=owned()
for pid,args in before:
 try:os.kill(pid,signal.SIGTERM)
 except ProcessLookupError:pass
if before:time.sleep(2)
for pid,args in owned():
 try:os.kill(pid,signal.SIGKILL)
 except ProcessLookupError:pass
if before:time.sleep(1)
remaining=owned()
ps=subprocess.check_output(['ps','-eo','pid,args','-ww'],text=True);(ev/'final-processes-full-private.txt').write_text(ps)
recorded=set()
for name in ['build-child.json','diagnostic-child.json','url-child.json']:
 p=ev/name
 if p.exists():recorded.add(json.loads(p.read_text())['pid'])
p=ev/'url-verification-results.json'
if p.exists():recorded.update(x['pid'] for x in json.loads(p.read_text()))
matching=[line for line in ps.splitlines()[1:] if int(line.strip().split(None,1)[0]) in recorded]
(ev/'final-processes.txt').write_text('ps -eo pid,args -ww: recorded process check\n'+('\n'.join(matching) if matching else 'No recorded Maven or consumer PID remains.')+'\nLane working-directory scan: '+str(remaining)+'\n')
(ev/'process-cleanup.json').write_text(json.dumps(dict(terminated=before,remaining=remaining),indent=2)+'\n')
print(json.dumps(dict(terminated_count=len(before),remaining=remaining)))
assert not remaining,'Lane-owned background process remains'
