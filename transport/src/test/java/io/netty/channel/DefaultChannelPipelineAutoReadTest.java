/*
 * Copyright 2026 The Netty Project
 *
 * The Netty Project licenses this file to you under the Apache License,
 * version 2.0 (the "License"); you may not use this file except in compliance
 * with the License. You may obtain a copy of the License at:
 *
 *   https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 */
package io.netty.channel;

import io.netty.bootstrap.Bootstrap;
import io.netty.bootstrap.ServerBootstrap;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import io.netty.channel.local.LocalAddress;
import io.netty.channel.local.LocalChannel;
import io.netty.channel.local.LocalIoHandler;
import io.netty.channel.local.LocalServerChannel;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

@Timeout(15)
public class DefaultChannelPipelineAutoReadTest {
    @Test
    public void activationCanLeaveAutomaticReadsToTheChannel() throws Exception {
        try (LocalConnection connection = new LocalConnection(new ManualReadLocalChannel())) {
            assertTrue(connection.channel.config().isAutoRead());
            assertEquals(0, connection.channel.reads.get(), "Activation must respect the automatic-read policy");
        }
        try (LocalConnection connection = new LocalConnection(new CountingLocalChannel())) {
            assertEquals(1, connection.channel.reads.get(), "The default pipeline must still read on activation");
        }
    }

    @Test
    public void readCompleteCanLeaveAutomaticReadsToTheChannel() throws Exception {
        try (LocalConnection connection = new LocalConnection(new ManualReadLocalChannel())) {
            connection.channel.reads.set(0);
            connection.channel.read();
            connection.sendOneByte();
            assertEquals(1, connection.channel.reads.get(), "Read completion must not add an automatic read");
        }
        try (LocalConnection connection = new LocalConnection(new CountingLocalChannel())) {
            connection.channel.reads.set(0);
            connection.sendOneByte();
            assertEquals(1, connection.channel.reads.get(), "The default pipeline must still read after completion");
        }
    }

    @Test
    public void activeReregistrationCanLeaveAutomaticReadsToTheChannel() throws Exception {
        try (LocalConnection connection = new LocalConnection(new ManualReadLocalChannel())) {
            connection.channel.reads.set(0);
            connection.reregister();
            assertEquals(0, connection.channel.reads.get(), "Re-registration must respect the automatic-read policy");
        }
        try (LocalConnection connection = new LocalConnection(new CountingLocalChannel())) {
            connection.channel.reads.set(0);
            connection.reregister();
            assertEquals(1, connection.channel.reads.get(), "The default pipeline must still read on re-registration");
        }
    }

    @Test
    public void explicitChannelAndContextReadsRemainAvailableWhenPaused() throws Exception {
        try (LocalConnection connection = new LocalConnection(new ManualReadLocalChannel())) {
            assertEquals(0, connection.channel.reads.get(), "Activation must not create manual demand");
            connection.channel.config().setAutoRead(false);
            connection.channel.read();
            connection.channel.pipeline().context("receiver").read();
            connection.settle();
            assertEquals(2, connection.channel.reads.get(), "Both public explicit-read paths must reach the channel");
            assertFalse(connection.channel.config().isAutoRead());
            connection.sendOneByte();
            assertEquals(2, connection.channel.reads.get(), "Read completion must leave the explicit demand unchanged");
        }
    }

    private static class CountingLocalChannel extends LocalChannel {
        final AtomicInteger reads = new AtomicInteger();

        @Override
        protected void doBeginRead() throws Exception {
            reads.incrementAndGet();
            super.doBeginRead();
        }
    }

    private static final class ManualReadLocalChannel extends CountingLocalChannel {
        @Override
        protected DefaultChannelPipeline newChannelPipeline() {
            return new DefaultChannelPipeline(this) {
                // No @Override so the regression also compiles against the original implementation.
                protected boolean shouldAutoRead() {
                    return false;
                }
            };
        }
    }

    private static final class LocalConnection implements AutoCloseable {
        final CountingLocalChannel channel;
        private final EventLoopGroup group = new MultiThreadIoEventLoopGroup(1, LocalIoHandler.newFactory());
        private final CompletableFuture<Channel> accepted = new CompletableFuture<Channel>();
        private final CompletableFuture<Void> delivered = new CompletableFuture<Void>();
        private Channel listener;
        private Channel peer;

        LocalConnection(CountingLocalChannel channel) throws Exception {
            this.channel = channel;
            try {
                listener = new ServerBootstrap().group(group).channel(LocalServerChannel.class)
                        .childHandler(new ChannelInboundHandlerAdapter() {
                            @Override
                            public void channelActive(ChannelHandlerContext ctx) {
                                accepted.complete(ctx.channel());
                                ctx.fireChannelActive();
                            }
                        }).bind(LocalAddress.ANY).sync().channel();
                new Bootstrap().group(group).channelFactory(() -> channel)
                        .handler(new ChannelInitializer<Channel>() {
                            @Override
                            protected void initChannel(Channel ch) {
                                ch.pipeline().addLast("receiver", new SimpleChannelInboundHandler<ByteBuf>() {
                                    @Override
                                    protected void channelRead0(ChannelHandlerContext ctx, ByteBuf msg) {
                                        assertEquals(1, msg.readableBytes());
                                        assertEquals(42, msg.readUnsignedByte());
                                    }

                                    @Override
                                    public void channelReadComplete(ChannelHandlerContext ctx) {
                                        delivered.complete(null);
                                        ctx.fireChannelReadComplete();
                                    }

                                    @Override
                                    public void exceptionCaught(ChannelHandlerContext ctx, Throwable cause) {
                                        delivered.completeExceptionally(cause);
                                    }
                                });
                            }
                        }).connect(listener.localAddress()).sync();
                peer = accepted.get(5, TimeUnit.SECONDS);
                settle();
            } catch (Exception cause) {
                close();
                throw cause;
            }
        }

        void sendOneByte() throws Exception {
            peer.writeAndFlush(Unpooled.wrappedBuffer(new byte[] { 42 })).sync();
            delivered.get(5, TimeUnit.SECONDS);
            settle();
        }

        void reregister() throws Exception {
            channel.deregister().sync();
            group.register(channel).sync();
            settle();
        }

        void settle() throws Exception {
            channel.eventLoop().submit(() -> { }).get(5, TimeUnit.SECONDS);
        }

        @Override
        public void close() {
            channel.close().syncUninterruptibly();
            if (peer != null) {
                peer.close().syncUninterruptibly();
            }
            if (listener != null) {
                listener.close().syncUninterruptibly();
            }
            group.shutdownGracefully(0, 5, TimeUnit.SECONDS).syncUninterruptibly();
        }
    }
}
