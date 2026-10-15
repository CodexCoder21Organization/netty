/*
 * Copyright 2026 The Netty Project
 * The Netty Project licenses this file under the Apache License, version 2.0.
 */
package io.netty.channel.nio;

import io.netty.channel.Channel;
import io.netty.channel.ChannelFuture;
import io.netty.channel.EventLoop;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.MultiThreadIoEventLoopGroup;
import io.netty.channel.socket.nio.NioSocketChannel;
import org.junit.jupiter.api.Test;

import java.nio.channels.SocketChannel;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class ShutdownReentryReviewTest {
    @Test
    public void closeListenersRegisteringMoreChannelsCannotLeaveAcceptedChannelsOpen() throws Exception {
        EventLoopGroup group = new MultiThreadIoEventLoopGroup(1, NioIoHandler.newFactory());
        List<SocketChannel> sockets = new ArrayList<>();
        List<Channel> channels = new ArrayList<>();
        List<ChannelFuture> registrations = new ArrayList<>();
        try {
            EventLoop loop = group.next();
            for (int i = 0; i < 8; i++) {
                SocketChannel socket = SocketChannel.open();
                sockets.add(socket);
                channels.add(new NioSocketChannel(socket));
            }
            for (int i = 0; i < channels.size() - 1; i++) {
                final Channel next = channels.get(i + 1);
                channels.get(i).closeFuture().addListener(future -> registrations.add(loop.register(next)));
            }
            loop.submit(() -> {
                registrations.add(loop.register(channels.get(0)));
                group.shutdownGracefully(0, 5, TimeUnit.SECONDS);
            }).get(5, TimeUnit.SECONDS);
            assertTrue(group.terminationFuture().await(10, TimeUnit.SECONDS));
            for (ChannelFuture registration : registrations) {
                Channel channel = registration.channel();
                System.out.println("accepted=" + registration.isSuccess() + " open=" + channel.isOpen()
                        + " registered=" + channel.isRegistered());
                assertFalse(channel.isOpen(), "A channel accepted during shutdown must close before termination");
                assertTrue(channel.closeFuture().isDone());
                assertFalse(channel.isRegistered());
            }
        } finally {
            for (SocketChannel socket : sockets) {
                socket.close();
            }
            assertTrue(group.shutdownGracefully(0, 5, TimeUnit.SECONDS).await(10, TimeUnit.SECONDS));
        }
    }
}
