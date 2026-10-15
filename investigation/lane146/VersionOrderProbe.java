import coursierapi.Version;
import org.apache.maven.artifact.versioning.ComparableVersion;
public class VersionOrderProbe {
 public static void main(String[] args) {
  System.out.println("coursierapi origin="+Version.class.getProtectionDomain().getCodeSource().getLocation());
  for(String v: args) System.out.println(v+" coursier="+Version.compare(v,"4.2.10.Final")+" maven="+new ComparableVersion(v).compareTo(new ComparableVersion("4.2.10.Final")));
 }
}
