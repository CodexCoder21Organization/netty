from pathlib import Path
import subprocess,os
lane=Path.cwd();root=lane/'toolchain/root';wrappers=lane/'toolchain/bin';wrappers.mkdir(exist_ok=True)
for name in ['libjansson4','libgprofng0']:
 for p in (lane/'toolchain/debs').glob(name+'_*'):subprocess.run(['dpkg-deb','-x',str(p),str(root)],check=True)
# Relocate Debian's script data paths; this affects only extracted lane-owned tools.
for p in (root/'usr/bin').glob('*'):
 if p.is_file() and not p.is_symlink():
  data=p.read_bytes()
  if data.startswith(b'#!'):
   text=data.decode(errors='strict').replace('/usr/share/',str(root/'usr/share')+'/')
   p.write_text(text)
for name,real in [('aclocal','aclocal-1.16'),('automake','automake-1.16')]:
 p=wrappers/name;p.write_text('#!/bin/sh\nexec '+str(root/'usr/bin'/real)+' "$@"\n');p.chmod(0o755)
for name in ['ninja','ninja-build']:
 p=wrappers/name;p.write_text('#!/bin/sh\nexec '+str(root/'usr/bin/ninja')+' -j1 "$@"\n');p.chmod(0o755)
p=wrappers/'cargo';p.write_text('#!/bin/sh\nexport CARGO_BUILD_JOBS=1\nexec '+str(lane/'toolchain/cargo/bin/cargo')+' "$@"\n');p.chmod(0o755)
env=dict(os.environ,PATH=str(wrappers)+':'+str(root/'usr/bin')+':'+os.environ['PATH'],LD_LIBRARY_PATH=str(root/'usr/lib/x86_64-linux-gnu'))
subprocess.run([str(wrappers/'gcc'),'-x','c','-','-o',str(lane/'toolchain/hello')],input=b'#include <stdio.h>\nint main(void){puts("compiler ready");}\n',check=True,env=env)
subprocess.run([str(lane/'toolchain/hello')],check=True,env=env)
