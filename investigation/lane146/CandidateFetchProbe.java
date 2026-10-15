import coursierapi.*;
public class CandidateFetchProbe {
 public static void main(String[] args) throws Exception {
  String v=args[0];
  System.out.println("API_CLASS_ORIGIN="+Fetch.class.getProtectionDomain().getCodeSource().getLocation());
  Fetch f=Fetch.create().withRepositories(MavenRepository.of(args[1]),MavenRepository.of("https://kotlin.directory"),MavenRepository.of("https://repo1.maven.org/maven2")).addDependencies(Dependency.of("io.netty","netty-transport",v),Dependency.of("io.netty","netty-transport","4.2.10.Final"));
  if(args.length>2)f=f.withMainArtifacts(false);
  FetchResult r=f.fetchResult();
  for(Dependency d:r.getDependencies())System.out.println("SELECTED "+d);
  for(java.io.File p:r.getFiles())System.out.println("FILE "+p);
  if(!r.getDependencies().stream().anyMatch(d->d.getModule().getName().equals("netty-transport") && d.getVersion().equals(v)))throw new AssertionError("Requested custom transport lost mediation: "+v);
 }
}
