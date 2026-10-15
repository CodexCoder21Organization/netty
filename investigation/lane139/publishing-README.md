# community.kotlin.maven.artifact.publishing

CLI tool for copying a Maven artifact directory into a Maven repository.
Useful when you need a lightweight Maven artifact releaser / deployer to publish
build outputs into a remote or local repository without relying on Maven's
native release tooling.

## TODO
* There is currently a bug where the tool will only work if the SSH certificate is unencrypted (certificates with passwords are broken).

## Building

Use the build rule `community.kotlin.maven.artifact.publishing.buildFatJar` to produce a runnable jar:

```bash
scripts/build.bash community.kotlin.maven.artifact.publishing.buildFatJar ~/artifact-publisher.jar
```

## Running

The published tool can be run directly with coursier:

```bash
coursier launch community.kotlin.maven.artifact.publishing:community-kotlin-maven-artifact-publishing:0.0.6 \
  -r https://kotlin.directory -- \
  --workspace /path/to/workspace \
  --buildrule fully.qualified.buildRule \
  --api-url https://api.kotlin.directory/upload
```

Run the generated jar specifying the workspace containing the build rule that
produces the Maven artifact directory and the repository root. Pass `--help` to
print usage information:

```bash
java -jar artifact-publisher.jar \
  --workspace /path/to/workspace \
  --buildrule fully.qualified.buildRule \
  --maven-repository /path/to/repo
  [--port 22] \
  [--identity /path/to/id_rsa] \
  [--force] \
  [--verbose]
```

To build and run in one step:

```bash
scripts/build.bash community.kotlin.maven.artifact.publishing.buildFatJar --launch -- \
  --workspace /path/to/workspace \
  --buildrule fully.qualified.buildRule \
  --maven-repository /path/to/repo
```

When `--maven-repository` uses the form `user@host:path` the repository is
accessed over SFTP using the provided port and identity parameters, similar to
`scp`.
The remote path is canonicalized using SFTP's `realpath`. Paths starting with
`~` are first expanded to the user's home directory.

If the private key is encrypted the tool will prompt for the key's password. The
password is read without echoing the typed characters when possible.
Pass `--verbose` to print debug messages from the SSH connection.

Example uploading to a remote repository:

```bash
java -jar artifact-publisher.jar \
  --workspace ~/codeworkspace \
  --buildrule my.package.rule \
  --maven-repository root@198.199.106.165:~/jvmbuildrulesmaven \
  --port 23 \
  --identity ~/.ssh/jim_id_rsa_20170414.private \
  --force \
  --verbose
```

The artifact directory is recursively searched for exactly one POM file
describing the artifact. If no POM file or multiple POM files are found the
operation aborts. POM files that use the standard Maven `project` namespace are
supported.

Before copying any files the tool prints a list of actions that will be
performed and asks for confirmation. Use `--force` to skip the confirmation
step. Each copied file is printed as `/old/path -> /new/path`. If the
destination file already exists and differs from the source `(overridden)` is
appended.

## Publishing Workspace Dependencies

With `--workspace`/`--buildrule`, the tool builds the rule, reads the dependencies from the POM it produced, and
publishes the workspace artifacts among them first. A dependency counts as a workspace artifact when a
parameterless build rule in one of the workspace's `build.kts` files declares `@MavenArtifactCoordinates` for the
same `groupId:artifactId`; that rule is built and, if it produces exactly the depended-upon version, published
before the artifact that needs it. For example, in a workspace with

```kotlin
@MavenArtifactCoordinates("buildwatchman:build-watchman-library:")
fun buildLibraryMaven(): File { /* ... */ }

@MavenArtifactCoordinates("buildwatchman:build-watchman:")
fun buildMaven(): File { /* depends on buildLibraryMaven() */ }
```

publishing `--buildrule buildwatchman.buildMaven` publishes `build-watchman-library` (from `buildLibraryMaven`)
and then `build-watchman`.

- Every other dependency (no rule declares its coordinates, or the rule builds a different version) is skipped
  with a message saying it must already be available in the target repository.
- Each coordinate is published at most once per run, even when several artifacts depend on it.
- A dependency whose exact version already exists in the target repository is not published again: the HTTP API
  answers `409 Artifact already exists`, and in `--maven-repository` mode the version directory already holds its
  POM. Already-published versions are never overwritten on behalf of a dependent; `--force` only applies to the
  artifact named by `--buildrule`.
- Workspace artifacts that depend on each other in a cycle cannot be published in any order. The tool stops
  before uploading any of them with an error naming the chain, for example
  `Dependency cycle detected between workspace artifacts: a:a:1.0.0 (rule p.buildA) -> b:b:1.0.0 (rule p.buildB) -> a:a:1.0.0 (rule p.buildA).`
- If building or publishing any of these artifacts fails, the run stops there and the requested artifact is not
  published.

## Exit Status

The tool exits with status `0` only when the requested operation completed: every requested artifact was
published, the artifacts were listed, or `--help` was printed. Every failure exits with status `1` and prints a
line starting with `Error:` on standard error, including invalid arguments, a build failure, a rejected upload, a
requested artifact that already exists in the HTTP repository, a declined confirmation prompt (nothing is
published), and any unexpected error (reported with its type, message, and the first 40 stack frames).

## Publishing Pre-Built Artifacts

Use the `--artifact-dir` (or `-a`) flag to publish a pre-built artifact
directory without rebuilding. This is useful when you have already built your
artifact (e.g., via Gradle) and just want to publish it to a Maven repository.

```bash
java -jar artifact-publisher.jar \
  --artifact-dir /path/to/built/artifact \
  --maven-repository /path/to/repo \
  [--force]
```

The artifact directory must contain:
- Exactly one `.pom` file describing the artifact
- The corresponding `.jar` file(s)

Example publishing a Gradle-built artifact:

```bash
# First, build with Gradle
./gradlew :my-module:jar

# Then publish the artifact directory
java -jar artifact-publisher.jar \
  --artifact-dir ./my-module/build/libs \
  --maven-repository root@myserver.com:~/maven-repo \
  --identity ~/.ssh/id_rsa \
  --force
```

Note: You cannot use `--artifact-dir` together with `--workspace`/`--buildrule`.

## Publishing via HTTP API

Use the `--api-url` flag to publish artifacts via an HTTP API endpoint instead
of SSH/SFTP. This is useful when you have a web service that handles artifact
uploads, such as https://api.kotlin.directory/upload.

```bash
java -jar artifact-publisher.jar \
  --artifact-dir /path/to/built/artifact \
  --api-url https://api.kotlin.directory/upload \
  [--force] \
  [--verbose]
```

Or with workspace/buildrule:

```bash
java -jar artifact-publisher.jar \
  --workspace /path/to/workspace \
  --buildrule fully.qualified.buildRule \
  --api-url https://api.kotlin.directory/upload \
  [--force]
```

The tool creates a tar.gz archive of the artifact directory with the proper
Maven repository structure (groupId/artifactId/version/files) and uploads it
to the specified URL. The API is expected to return a JSON response with:

```json
{
  "success": true,
  "installed": ["groupId:artifactId:version"]
}
```

Pass `--verbose` to see upload progress and response details. The upload
automatically retries up to 3 times on transient failures (connection errors and
HTTP 5xx responses) with exponential backoff. Client errors (HTTP 4xx) are not
retried.

Note: `--list-artifacts` is not supported with `--api-url`. Use
`--maven-repository` to list artifacts from a repository.

## Listing Artifacts

Use the `--list-artifacts` (or `-l`) flag to list all artifacts in a Maven
repository. Each artifact is printed in `group:artifact:version` format,
showing the latest version available for each artifact.

```bash
java -jar artifact-publisher.jar \
  --maven-repository /path/to/repo \
  --list-artifacts
```

For remote repositories:

```bash
java -jar artifact-publisher.jar \
  --maven-repository root@198.199.106.165:~/jvmbuildrulesmaven \
  --port 23 \
  --identity ~/.ssh/id_rsa \
  --list-artifacts
```

Example output:

```
com.example:my-library:1.2.3
com.example:other-lib:2.0.0
org.myorg:utils:0.5.1
```

## Example

The command line is also available as a function that returns the exit status instead of exiting the process:

```kotlin
import community.kotlin.maven.artifact.publishing.runArtifactPublisherCli

fun main() {
    val exitCode = runArtifactPublisherCli(
        arrayOf(
            "--workspace", "/path/to/workspace",
            "--buildrule", "my.package.buildMaven",
            "--maven-repository", "/tmp/repo",
            "--force",
        )
    )
    check(exitCode == 0) { "Publishing failed with exit status $exitCode" }
}
```

Installing an already-built artifact directory directly:

```kotlin
import community.kotlin.maven.artifact.publishing.installMavenArtifact
import okio.FileSystem
import okio.Path.Companion.toPath

fun main() {
    installMavenArtifact(
        FileSystem.SYSTEM,
        "/tmp/artifact".toPath(),
        FileSystem.SYSTEM,
        "/tmp/repo".toPath()
    )
}
```
