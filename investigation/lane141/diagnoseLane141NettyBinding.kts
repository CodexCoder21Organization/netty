@file:WithArtifact("foundation.url.protocol.buildMaven()")
@file:WithArtifact("io.netty:netty-all:4.2.10.Final-codexcoder21-1")
package foundation.url.protocol
import build.kotlin.withartifact.WithArtifact
import io.netty.channel.SingleThreadIoEventLoop
import io.netty.buffer.AdaptiveByteBufAllocator
import io.netty.util.Version
fun diagnoseLane141NettyBinding() {
    throw IllegalStateException("DIAGNOSTIC_ONLY transport=" + SingleThreadIoEventLoop::class.java.protectionDomain.codeSource.location + "; buffer=" + AdaptiveByteBufAllocator::class.java.protectionDomain.codeSource.location + "; versions=" + Version.identify())
}
