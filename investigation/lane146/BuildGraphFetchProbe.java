import coursierapi.*;
public class BuildGraphFetchProbe {
 public static void main(String[] args) throws Exception {
  String v=args[0];
  Fetch f=Fetch.create().withRepositories(MavenRepository.of("https://kotlin.directory"),MavenRepository.of("https://repo1.maven.org/maven2"))
   .addDependencies(Dependency.of("community.kotlin.libp2p","jvm-libp2p","1.3.0-codexcoder21-snapshot-25"));
  for(String name:new String[]{"netty-buffer","netty-common","netty-transport","netty-handler","netty-codec"})f=f.addDependencies(Dependency.of("io.netty",name,v));
  FetchResult r=f.fetchResult();int custom=0;
  for(Dependency d:r.getDependencies()) {
   System.out.println("SELECTED "+d);
   if(d.getModule().getOrganization().equals("io.netty") && !d.getModule().getName().startsWith("netty-tcnative") && !d.getModule().getName().equals("netty-jni-util")) {
    if(!d.getVersion().equals(v))throw new AssertionError("Unexpected core Netty version "+d);
    custom++;
   }
  }
  for(java.io.File p:r.getFiles())System.out.println("FILE "+p);
  if(custom==0)throw new AssertionError("No core Netty dependencies");
  System.out.println("CUSTOM_CORE_COUNT="+custom);
 }
}
