"""Run the public-API shutdown review test against published Netty artifacts.

Requires JDK 21 and ShutdownReentryReviewTest.java beside this file.
Expected result for 4.2.10.1-codexcoder21: one failed test and process exit 1.
Downloads live in a temporary directory and are removed after execution.
"""
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile

version = '4.2.10.1-codexcoder21'
commit = 'a66b8e41266dd9a8ae193cf3dea021b3b5547d7f'
source = Path(__file__).with_name('ShutdownReentryReviewTest.java')
with tempfile.TemporaryDirectory(prefix='netty-reentry-review-') as directory:
    root = Path(directory)
    jars = []
    for module in ['transport', 'buffer', 'common', 'resolver']:
        artifact = 'netty-' + module
        jar = root / (artifact + '.jar')
        url = f'https://kotlin.directory/io/netty/{artifact}/{version}/{artifact}-{version}.jar'
        with urllib.request.urlopen(url, timeout=45) as response:
            jar.write_bytes(response.read())
        with zipfile.ZipFile(jar) as archive:
            metadata = archive.read('META-INF/io.netty.versions.properties').decode()
            assert f'{artifact}.longCommitHash={commit}' in metadata, metadata
            assert f'{artifact}.repoStatus=clean' in metadata, metadata
        jars.append(str(jar))
    console = root / 'junit-console.jar'
    url = ('https://repo.maven.apache.org/maven2/org/junit/platform/'
           'junit-platform-console-standalone/1.14.3/junit-platform-console-standalone-1.14.3.jar')
    with urllib.request.urlopen(url, timeout=45) as response:
        console.write_bytes(response.read())
    classes = root / 'classes'
    classes.mkdir()
    classpath = ':'.join([str(console), *jars])
    subprocess.run(['javac', '-cp', classpath, '-d', str(classes), str(source)],
                   check=True, timeout=60)
    result = subprocess.run(['java', '-Xmx128m', '-jar', str(console), 'execute',
                             '--class-path', ':'.join([str(classes), *jars]),
                             '--select-class', 'io.netty.channel.nio.ShutdownReentryReviewTest',
                             '--details=verbose'], timeout=30)
    exit_code = result.returncode
raise SystemExit(exit_code)
