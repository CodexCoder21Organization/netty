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

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.condition.EnabledForJreRange;
import org.junit.jupiter.api.condition.JRE;
import org.junit.jupiter.api.parallel.Isolated;

@Timeout(10)
@EnabledForJreRange(min = JRE.JAVA_17) // RecordingStream
@Isolated
public class JfrEventsTest {
    @Test
    public void adaptiveDoesNotRegisterEventsWithoutARecorder() throws Exception {
        AllocatorJfrColdStartHarness.runChild("adaptive", "inactive");
    }

    @Test
    public void pooledDoesNotRegisterEventsWithoutARecorder() throws Exception {
        AllocatorJfrColdStartHarness.runChild("pooled", "inactive");
    }

    @Test
    public void adaptiveRecordsWhenEnabledByNameAfterBufferUse() throws Exception {
        AllocatorJfrColdStartHarness.runChild("adaptive", "active");
    }

    @Test
    public void pooledRecordsWhenEnabledByNameAfterBufferUse() throws Exception {
        AllocatorJfrColdStartHarness.runChild("pooled", "active");
    }

}
