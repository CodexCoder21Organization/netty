import coursierapi.*;
public class ConsumerFetchProbe {
 public static void main(String[] args) throws Exception {
  System.out.println("API_CLASS_ORIGIN="+Fetch.class.getProtectionDomain().getCodeSource().getLocation());
  Fetch f=Fetch.create().withRepositories(MavenRepository.of(args[1]),MavenRepository.of("https://kotlin.directory"),MavenRepository.of("https://repo1.maven.org/maven2"))
   .addDependencies(Dependency.of("community.kotlin.libp2p","jvm-libp2p","1.3.0-codexcoder21-snapshot-25"),Dependency.of("io.netty","netty-transport",args[0])).withMainArtifacts(false);
  FetchResult r=f.fetchResult();
  for(Dependency d:r.getDependencies())System.out.println("SELECTED "+d);
 }
}
