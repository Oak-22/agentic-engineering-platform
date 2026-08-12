Markdown
# Agentic Engineering Platform: Physical Telemetry Extension Specification

## Executive Summary
This document outlines the architectural extension for the **Inference Telemetry Observatory** component within the Agentic Engineering Platform. By bridging low-level hardware performance indicators with high-level agentic orchestration events, this system enables precise unit economics calculation, hardware-aware cognitive routing, and fine-grained latency bottleneck diagnosis.

---

## 1. High-Level Architecture

The extension introduces a sidecar collector daemon alongside the core inference engine to capture real-time host and accelerator metrics, correlating them directly with higher-order agent traces.

+-----------------------------------------------------------------------------------+
|                            AGENTS & ORCHESTRATION LAYER                            |
|  [Agent Execution Step] ---> [Trace / Span ID] ---> [Cognitive Router]            |
+-----------------------------------------------------------------------------------+
|
Telemetry Context
v
+-----------------------------------------------------------------------------------+
|                        INFERENCE TELEMETRY OBSERVATORY                            |
|                                                                                   |
|  +---------------------------+         +---------------------------------------+  |
|  |   Logical Telemetry Logs  |         |     Physical Telemetry Collector      |  |
|  | (Tokens, Prompts, Tools)  |         |   (NVML, ROCm-SMI, RAPL, TPU Profiler) |  |
|  +---------------------------+         +---------------------------------------+  |
|                \                                     /                            |
|                 +-----------------+-----------------+                             |
|                                   |                                               |
|                                   v                                               |
|               [Correlated Event Schema & Aggregator]                              |
|                                   |                                               |
+-----------------------------------|-----------------------------------------------+
v
+-----------------------------------------------------------------------------------+
|                       ANALYTICS & STORAGE LAYER (ClickHouse / DuckDB)             |
+-----------------------------------------------------------------------------------+


---

## 2. Metric Specifications

The Physical Telemetry Observatory collects telemetry across four core domains, mapped directly to specific `agent_step_id` and `trace_id` contexts.

### 2.1 Memory & Bandwidth Metrics
* **Metrics Tracked:** SRAM/HBM utilization percentage, memory bus bandwidth usage, KV cache allocation memory pressure.
* **Collection Sources:** `pynvml` (`nvmlDeviceGetMemoryInfo`), ROCm-SMI, TPU Profiler APIs.
* **Diagnostic Focus:** Differentiates whether step-level execution delays stem from compute latency (FLOP bound) or memory bandwidth ceilings (HBM transfer bound during KV cache hydration or context loading).

### 2.2 Energy & Unit Economics Metrics
* **Metrics Tracked:** Real-time wattage, Joules/milliwatt-hours ($mWh$) per generated token, energy cost per execution step.
* **Collection Sources:** Running Average Power Limit (RAPL) via `/sys/class/powercap`, NVML (`nvmlDeviceGetPowerUsage`).
* **Diagnostic Focus:** Establishes true physical cost accounting ($mWh$) per reasoning loop, allowing direct comparison between single-pass generation vs. multi-agent tree search strategies.

### 2.3 System Bus & Interconnect Metrics
* **Metrics Tracked:** PCIe bandwidth utilization, NVLink/InfiniBand transport throughput, host-to-accelerator data transfer delays.
* **Collection Sources:** NVML, InfiniBand diagnostics (`ibstat`), OS socket instrumentation.
* **Diagnostic Focus:** Detects IPC bottlenecks and IPC transport overhead when transferring large system prompts, tool payloads, or model weights between host CPU RAM and VRAM.

### 2.4 Thermal & Hardware Dynamics
* **Metrics Tracked:** Accelerator die temperature, core/memory clock frequency scaling, thermal throttling state bit.
* **Collection Sources:** Low-level hardware SMI interfaces.
* **Diagnostic Focus:** Monitors system stability during sustained, multi-hour autonomous execution chains and high-batch multi-agent evaluations.

---

## 3. Data Schema Definition

Physical telemetry events are structured as JSON-line payloads prior to ingestion into analytical storage engines (e.g., ClickHouse, DuckDB, or TimescaleDB).

```json
{
  "timestamp": "2026-08-11T09:53:17.000Z",
  "trace_id": "tr_9f8a2b1c0d",
  "span_id": "sp_4e3d2c1b0a",
  "agent_step_id": "step_code_optimization_pass_2",
  "agent_name": "RefactoringAgent",
  "model_identifier": "local-glm-5.2-q4",
  "logical_telemetry": {
    "prompt_tokens": 4096,
    "completion_tokens": 512,
    "total_latency_ms": 1240.5,
    "tool_calls_count": 2,
    "cache_hit": true
  },
  "physical_telemetry": {
    "accelerator_id": "gpu:0",
    "gpu_utilization_pct": 88.5,
    "hbm_bandwidth_utilization_pct": 94.2,
    "power_draw_watts": 320.4,
    "energy_consumed_joules": 397.46,
    "energy_per_completion_token_mwh": 0.215,
    "temperature_celsius": 68.0,
    "clock_throttle_active": false,
    "pcie_throughput_mbps": 1420.0
  }
}
4. Hardware-Aware Routing Mechanics
Captured physical telemetry actively informs the cognitive orchestration layer to optimize system efficiency:

Memory-Pressure Throttling: When HBM bandwidth utilization exceeds 90% or VRAM allocation reaches critical thresholds, the orchestrator routes secondary tool validation loops to quantized, low-power local instances or delegates context pruning steps.

Dynamic Context Scaling: Adjusts maximum context window sizing and parallel branch factors dynamically based on real-time memory bus and interconnect headroom.

Power Budget Allocation: Limits max execution branches during multi-agent search loops if power draw constraints or thermal throttling limits are encountered.