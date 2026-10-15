import coursierapi.*;
public class CoursierVersionProbe {
 public static void main(String[] args) throws Exception {
  System.out.println("API_CLASS_ORIGIN=" + Fetch.class.getProtectionDomain().getCodeSource().getLocation());
  for (java.io.File f: Fetch.create().withRepositories(MavenRepository.of("https://kotlin.directory"), MavenRepository.of("https://repo1.maven.org/maven2")).addDependencies(Dependency.of("io.netty","netty-transport","4.2.10.Final-codexcoder21-1"),Dependency.of("io.netty","netty-transport","4.2.10.Final")).fetch()) System.out.println(f);
 }
}
