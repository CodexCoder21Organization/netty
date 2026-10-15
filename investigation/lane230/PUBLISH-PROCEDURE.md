# Supervisor publication procedure (not executed by lane230)

Lane222 established that all 46 published POMs and 44 main jars at 4.2.10.1-codexcoder21 came from a66b8e41. Its findings do not contain an upload command. The build/staging procedure below is the actual prior release procedure from [lane146 build_release.py](https://github.com/CodexCoder21Organization/netty/blob/evidence/lane146-version-selection/investigation/lane146/build_release.py) and [assemble_artifacts.py](https://github.com/CodexCoder21Organization/netty/blob/evidence/lane146-version-selection/investigation/lane146/assemble_artifacts.py), with only version, cache and output paths adapted. Upload uses the publisher's documented prebuilt-artifact mode.

After review/merge and authorization to publish, use a fresh checkout of maint/4.2.10-codexcoder21 containing this release. Build with JDK 21, C/C++/make/autotools, CMake/Ninja, Rust/Cargo and Go available. Native work must be serial (CARGO_BUILD_JOBS=1, CMAKE_BUILD_PARALLEL_LEVEL=1, ninja -j1). Use one JVM-heavy command at a time and 2 GiB JVM heap. Do not reuse 4.2.10.1 coordinates.

With netty checkout, m2 and the adapted assembly script as siblings in a fresh working directory:

```bash
export JAVA_HOME=/usr/lib/jvm/temurin-21-jdk-amd64
export JAVA_OPTS=-Xmx2g MAVEN_OPTS=-Xmx2g JAVA_TOOL_OPTIONS=-Xmx2g
export CARGO_BUILD_JOBS=1 CMAKE_BUILD_PARALLEL_LEVEL=1
# From the directory containing netty/, create this lane-private cache path:
release_m2="$PWD/m2"
cd netty
git fetch origin
git rebase origin/maint/4.2.10-codexcoder21
./mvnw -e -B -Dmaven.repo.local="$release_m2" -f bom/pom.xml -DskipTests install
./mvnw -e -B -Dmaven.repo.local="$release_m2" -pl common,buffer,transport,handler,codec,all -am -DskipTests install
./mvnw -e -B -Dmaven.repo.local="$release_m2" -pl common,transport test
cd ..
gh api 'repos/CodexCoder21Organization/netty/contents/investigation/lane230/assemble-artifacts.py?ref=evidence/lane230-netty-release' -q .content | base64 -d > assemble-artifacts.py
python3 assemble-artifacts.py
```

Require 46 module directories and 136 POM/JAR payloads, one POM in each directory, and matching SHA1/SHA256 files. Inspect staged-artifacts/MANIFEST.txt and CUSTOM-DEPENDENCIES.json; parent first, BOM second, dependencies before consumers and netty-all last. Verify jar version metadata records the clean approved source commit and version 4.2.10.2-codexcoder21. Verify the intended .2 coordinates are not already occupied; never replace existing release bytes.

Only when the supervisor is ready to publish, run this from the directory containing staged-artifacts. Each invocation uploads exactly one artifact directory, and the procedure stops on the first failed upload:

```python
from pathlib import Path
import json, subprocess
stage = Path('staged-artifacts').resolve()
order = json.loads((stage / 'CUSTOM-DEPENDENCIES.json').read_text())['publish_order']
assert len(order) == 46
for module in order:
    subprocess.run([
        '/home/helena/bin/coursier', 'launch',
        'community.kotlin.maven.artifact.publishing:community-kotlin-maven-artifact-publishing:0.0.6',
        '-r', 'https://kotlin.directory', '--',
        '--artifact-dir', str(stage / module),
        '--api-url', 'https://api.kotlin.directory/upload', '--force'
    ], check=True)
```

After all 46 invocations succeed, read back every POM and main jar plus the platform classifier jars, check version/commit metadata and hashes, then update UrlProtocol pins in a separate follow-up. No artifact was published by lane230.
