#!/usr/bin/python
# Copyright 2023, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import json
import re
import unittest
from datetime import datetime, timedelta

metric_to_stat_dict = {
    "request_type=context": "Context Requests per Iteration",
    "request_type=scheduled": "Scheduled Requests per Iteration",
    "request_type=max": "Max Request Count",
    "request_type=active": "Active Request Count",
    "memory_type=pinned": "Runtime Pinned Memory Usage",
    "memory_type=gpu": "Runtime GPU Memory Usage",
    "memory_type=cpu": "Runtime CPU Memory Usage",
    "kv_cache_block_type=tokens_per": "Tokens per KV cache block",
    "kv_cache_block_type=used": "Used KV cache blocks",
    "kv_cache_block_type=free": "Free KV cache blocks",
    "kv_cache_block_type=max": "Max KV cache blocks",
    "inflight_batcher_specific_metric=total_context_tokens":
    "Total Context Tokens per Iteration",
    "inflight_batcher_specific_metric=micro_batch_id": "MicroBatch ID",
    "inflight_batcher_specific_metric=generation_requests":
    "Generation Requests per Iteration",
    "v1_specific_metric=total_context_tokens":
    "Total Context Tokens per Iteration",
    "v1_specific_metric=total_generation_tokens":
    "Total Generation Tokens per Iteration",
    "v1_specific_metric=empty_generation_slots": "Empty Generation Slots",
    "general_type=iteration_counter": "Iteration Counter",
    "general_type=timestamp": "Timestamp",
}


class TRTLLMStatsTest(unittest.TestCase):

    def _parse_log_file(self, filename):
        with open(filename) as log_file:
            for line in reversed(list(log_file)):
                if "Active Request Count" in line:
                    json_format = re.sub(r"^.*?{", "{", line)
                    return json.loads(json_format)

    def _parse_triton_metrics(self, filename, is_v1):
        curl_counts = {}
        with open(filename) as metrics_file:
            for line in metrics_file:
                metric_value = ""
                if line[0] != "#" and "nv_trt_llm" in line:
                    metric_output = re.sub(r"^.*?{", "{", line).split()
                    metric_key = metric_output[0]
                    metric_value = metric_output[1]
                    key = self._convert_metric_key_to_stats_key(
                        metric_key, is_v1)
                    curl_counts[key] = metric_value
        return curl_counts

    def _convert_metric_key_to_stats_key(self, metric_output, is_v1):
        # Converts:
        # '{model="tensorrt_llm",request_type="context",version="1"}'
        # to:
        # ['model=tensorrt_llm', 'request_type=context', 'version=1']
        base = metric_output.replace('"', "").strip("{}").split(",")
        key = [
            i for i in base
            if not i.startswith('model') and not i.startswith('version')
        ][0]
        self.assertIn(key, metric_to_stat_dict)
        if (is_v1):
            self.assertNotIn("inflight_batcher_specific_metric", key)
        else:
            self.assertNotIn("v1_specific_metric", key)
        return metric_to_stat_dict[key]

    def _base_test(self, stats_file, metrics_file, is_v1):
        stats = self._parse_log_file(stats_file)
        metrics = self._parse_triton_metrics(metrics_file, is_v1)
        self.assertEqual(len(stats.keys()), len(metrics.keys()))
        self.assertEqual(
            list(stats.keys()).sort(),
            list(metrics.keys()).sort())
        for metric_key in stats.keys():
            if metric_key != "Timestamp":
                self.assertEqual(int(stats[metric_key]),
                                 int(metrics[metric_key]))
            else:
                dt_log = datetime.strptime(stats[metric_key],
                                           "%m-%d-%Y %H:%M:%S")
                dt_curl = datetime.utcfromtimestamp(
                    int(metrics[metric_key]) // 1000000)
                difference = dt_log - dt_curl
                self.assertTrue(
                    timedelta(seconds=-1) <= difference,
                    difference <= timedelta(seconds=1))

    def test_1_gpu_v1(self):
        self._base_test("1gpu_v1_no_streaming_server.log",
                        "1gpu_v1_no_stream_metrics.out", True)

    def test_1_gpu_IFB_no_stream(self):
        self._base_test("1gpu_IFB_no_streaming_server.log",
                        "1gpu_IFB_no_stream_metrics.out", False)

    def test_1_gpu_IFB_stream(self):
        self._base_test("1gpu_IFB_streaming_server.log",
                        "1gpu_IFB_stream_metrics.out", False)

    def test_2_gpu_v1(self):
        self._base_test("2gpu_v1_no_streaming_server.log",
                        "2gpu_v1_no_stream_metrics.out", True)

    def test_2_gpu_IFB_no_stream(self):
        self._base_test("2gpu_IFB_no_streaming_server.log",
                        "2gpu_IFB_no_stream_metrics.out", False)

    def test_2_gpu_IFB_stream(self):
        self._base_test("2gpu_IFB_streaming_server.log",
                        "2gpu_IFB_stream_metrics.out", False)

    def test_4_gpu_v1(self):
        self._base_test("4gpu_v1_no_streaming_server.log",
                        "4gpu_v1_no_stream_metrics.out", True)

    def test_4_gpu_IFB_no_stream(self):
        self._base_test("4gpu_IFB_no_streaming_server.log",
                        "4gpu_IFB_no_stream_metrics.out", False)

    def test_4_gpu_IFB_stream(self):
        self._base_test("4gpu_IFB_streaming_server.log",
                        "4gpu_IFB_stream_metrics.out", False)


if __name__ == "__main__":
    unittest.main()
