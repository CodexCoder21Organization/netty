@file:WithArtifact("foundation.url.protocol.buildMaven()")
@file:WithArtifact("io.netty:netty-all:4.2.10.1-codexcoder21")
package foundation.url.protocol
import build.kotlin.withartifact.WithArtifact
import io.netty.channel.SingleThreadIoEventLoop
import io.netty.buffer.AdaptiveByteBufAllocator
import io.netty.util.NettyRuntime
import io.netty.util.Version
fun diagnoseLane146NettyBinding() {
    val transport = SingleThreadIoEventLoop::class.java.protectionDomain.codeSource.location.toString()
    val buffer = AdaptiveByteBufAllocator::class.java.protectionDomain.codeSource.location.toString()
    val common = NettyRuntime::class.java.protectionDomain.codeSource.location.toString()
    println("DIAGNOSTIC_ONLY transport=$transport; buffer=$buffer; common=$common; versions=" + Version.identify())
    for ((module, origin) in listOf("transport" to transport, "buffer" to buffer, "common" to common)) {
        check(origin.contains("/4.2.10.1-codexcoder21/") && origin.endsWith("-4.2.10.1-codexcoder21.jar")) {
            "Expected rebuilt custom Netty $module at 4.2.10.1-codexcoder21, but loaded $origin"
        }
    }
}
