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
package io.netty.buffer;

import jdk.jfr.FlightRecorder;
import jdk.jfr.consumer.RecordedEvent;
import jdk.jfr.consumer.RecordingStream;
import org.junit.jupiter.api.Test;

import java.nio.file.Paths;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class AllocatorJfrColdStartTest {
    @Test
    public void adaptiveDoesNotRegisterEventsWithoutARecorder() throws Exception {
        runChild("adaptive", "inactive");
    }

    @Test
    public void pooledDoesNotRegisterEventsWithoutARecorder() throws Exception {
        runChild("pooled", "inactive");
    }

    @Test
    public void adaptiveRecordsWhenEnabledByNameAfterBufferUse() throws Exception {
        runChild("adaptive", "active");
    }

    @Test
    public void pooledRecordsWhenEnabledByNameAfterBufferUse() throws Exception {
        runChild("pooled", "active");
    }

    private static void runChild(String allocator, String mode) throws Exception {
        Process process = new ProcessBuilder(
                Paths.get(System.getProperty("java.home"), "bin", "java").toString(),
                "-Xmx128m", "-XX:+UseSerialGC", "-cp", System.getProperty("java.class.path"),
                AllocatorJfrColdStartTest.class.getName(), allocator, mode).redirectErrorStream(true).start();
        java.util.concurrent.ExecutorService reader = java.util.concurrent.Executors.newSingleThreadExecutor();
        try {
            java.util.concurrent.Future<String> output = reader.submit(() -> {
                try (java.io.InputStream stream = process.getInputStream()) {
                    java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                    byte[] chunk = new byte[4096];
                    for (int size; (size = stream.read(chunk)) != -1;) {
                        bytes.write(chunk, 0, size);
                    }
                    return bytes.toString("UTF-8");
                }
            });
            assertTrue(process.waitFor(30, TimeUnit.SECONDS), "Cold allocator child did not finish");
            String result = output.get(5, TimeUnit.SECONDS);
            assertEquals(0, process.exitValue(), result);
        } finally {
            if (process.isAlive()) {
                process.destroyForcibly();
                process.waitFor(5, TimeUnit.SECONDS);
            }
            reader.shutdownNow();
            assertTrue(reader.awaitTermination(5, TimeUnit.SECONDS), "Child output reader did not stop");
        }
    }

    public static void main(String[] args) throws Exception {
        assertTrue(!FlightRecorder.isInitialized(), "The child must start without a recorder");
        ByteBufAllocator allocator = "adaptive".equals(args[0]) ?
                new AdaptiveByteBufAllocator(true) : new PooledByteBufAllocator(true);
        allocateAndRelease(allocator);
        if ("inactive".equals(args[1])) {
            List<String> registered = FlightRecorder.getFlightRecorder().getEventTypes().stream()
                    .map(type -> type.getName()).filter(name -> name.startsWith("io.netty."))
                    .collect(Collectors.toList());
            assertTrue(registered.isEmpty(),
                    "Buffer use without a recorder registered allocator event types: " + registered);
        } else {
            try (RecordingStream stream = new RecordingStream()) {
                CompletableFuture<RecordedEvent> allocated = new CompletableFuture<>();
                stream.enable("io.netty.AllocateBuffer");
                stream.onEvent("io.netty.AllocateBuffer", allocated::complete);
                stream.startAsync();
                allocateAndRelease(allocator);
                assertEquals(32, allocated.get(5, TimeUnit.SECONDS).getInt("size"));
            }
        }
        System.out.println("ALLOCATOR_COLD_START_PASS " + args[0] + " " + args[1]);
    }

    private static void allocateAndRelease(ByteBufAllocator allocator) {
        for (boolean direct : new boolean[] {false, true}) {
            ByteBuf buffer = direct ? allocator.directBuffer(32, 1024) : allocator.heapBuffer(32, 1024);
            try {
                buffer.writeByte(7);
                buffer.capacity(256);
                assertEquals(7, buffer.getByte(0));
            } finally {
                assertTrue(buffer.release(), "The test owns the buffer's only reference");
            }
        }
    }
}
