# Cortex-R5 CTI SMP: Follow-up Improvement and Hardware Validation Plan

This plan captures the next iterations after landing CTI-based SMP halt/resume for Cortex-R4/R5 in `cortex_a` and is intended to be executable on real TI K3-class hardware (for example AM2434 + XDS110).

## 1) Functional improvements (implementation backlog)

### 1.1 CTI diagnostics and observability
- Add explicit debug traces for:
  - CTI channel gate/ungate transitions.
  - CTI pulse origin core.
  - group halt/restart convergence decision points.
  - fallback to legacy non-CTI SMP paths.
- Add a user-visible warning when SMP is enabled but one or more cores in the SMP list are missing `-cti` configuration.
- Add a compact per-core status dump command for Cortex-R SMP (debug state, CTI state, postponed event state).

### 1.2 Robustness / timeout handling
- Make CTI SMP convergence timeout configurable via target option (default remains 1000 ms).
- Emit a timeout summary that identifies which cores failed to converge.
- Add retry strategy for transient AP access failures during convergence polling (bounded retries with diagnostics).

### 1.3 SMP policy correctness and UX
- Ensure exactly one `TARGET_EVENT_HALTED` is emitted to GDB for a coordinated group halt, while retaining per-core internal state updates.
- Add clearer debug logs around postponed-halt-event queueing/flush behavior.
- Keep `cortex_a smp on/off` behavior deterministic when toggled mid-session.

### 1.4 Step and breakpoint semantics in SMP
- Validate and harden step-over-breakpoint behavior with CTI restart path:
  - single-step one halted core with peers halted.
  - resume all after step-over.
- Verify hardware/software breakpoint restore sequencing across all halted peers prior to synchronized restart pulse.

### 1.5 Configuration/documentation quality
- Extend board/target examples to include dual-cluster R5 systems and per-cluster SMP declarations.
- Add troubleshooting guidance for CTI routing misconfiguration (symptoms, expected logs, common fixes).

## 2) Code quality and maintainability tasks

- Add helper wrappers to consolidate repeated CTI gate/pulse/ack patterns.
- Reduce duplicated SMP iteration loops by introducing common iterators with policy flags (`running-only`, `halted-only`, `examined-only`).
- Add targeted unit-testable helpers for convergence checks and event-postpone policy where practical.

## 3) Detailed hardware validation plan

## 3.1 Test setup prerequisites

### Hardware
- TI AM2434 (or AM64x/AM263x variant with equivalent R5 clusters).
- Debug probe: XDS110 (or equivalent JTAG probe).
- Stable power/reset control and known-good wiring.

### Software
- Newly built OpenOCD binary from this branch.
- GDB matching target architecture (Arm none-eabi GDB for R5 firmware).
- Test firmware images:
  - `spin.elf`: all R5 cores run independent infinite loops with heartbeat counters.
  - `bkpt.elf`: deterministic breakpoint locations on each core.
  - `step.elf`: short deterministic instruction sequence for stepping checks.

### OpenOCD config baseline
- Use per-core `cti create` and bind each R5 target with `-cti`.
- Declare SMP per dual-core cluster (`target smp core0 core1`).
- Keep one configuration variant intentionally missing one `-cti` binding for negative testing.

## 3.2 Validation matrix

### A) Bring-up and configuration checks
1. Start OpenOCD with full CTI config.
2. Confirm all R5 targets can be examined.
3. Verify no CTI init failures in logs.

Expected:
- Successful examine on active cores.
- Debug logs show CTI enabled and channel programming.

### B) Group halt propagation
1. Run both cores in one SMP cluster.
2. Issue `halt` from OpenOCD/GDB on one core context.
3. Poll states of both cores.

Expected:
- Both cores halt within timeout window.
- One primary halt event observed by GDB.
- Logs show CH0 pulse and convergence completion.

### C) Group synchronized resume
1. With both cores halted, issue `resume`.
2. Poll both cores.

Expected:
- Both cores transition to running.
- Logs show HALT ack + CH1 pulse + convergence completion.
- No stale-halt immediate re-entry.

### D) Breakpoint hit behavior
1. Set shared and core-specific breakpoints.
2. Resume SMP cluster.
3. Trigger breakpoint on one core.

Expected:
- Cluster halts coherently according to configured SMP behavior.
- GDB reports a single coherent stop reason.
- Core selection remains consistent (`smp_gdb` semantics preserved).

### E) Single-step interaction
1. Halt cluster.
2. Single-step selected core.
3. Verify peer core behavior remains correct.

Expected:
- No unintended resume of peer unless policy requires coordinated restart.
- No duplicate halt notifications.

### F) Partial examination / unavailable core
1. Keep one core unpowered or unexamined (if platform supports).
2. Attempt SMP halt/resume on the cluster.

Expected:
- Examined/running peers converge.
- Graceful skip for unavailable core with clear logs.
- No deadlock.

### G) Negative CTI configuration
1. Remove `-cti` from one core in SMP group.
2. Re-run halt/resume scenarios.

Expected:
- Deterministic failure or fallback behavior per implementation policy.
- Clear diagnostic indicating missing CTI binding.

### H) Timeout stress
1. Introduce artificial delay/clock gating on one core (if possible).
2. Trigger group halt/resume.

Expected:
- Timeout triggers cleanly.
- Logs identify non-converged core(s).
- OpenOCD remains responsive for recovery operations.

## 3.3 Data capture template (per test run)

- OpenOCD commit hash:
- Board / SoC / silicon revision:
- Probe and firmware version:
- OpenOCD command line + config file set:
- Test case ID:
- Pass/Fail:
- OpenOCD log excerpt (CTI prep/pulse/convergence):
- GDB transcript excerpt:
- Notes / anomalies:

## 3.4 Exit criteria for production readiness

- All A–H scenarios pass on at least one dual-core R5 cluster.
- No regressions in non-CTI single-core operation.
- No duplicate halt callbacks in GDB-visible behavior during SMP group halt.
- Timeout and partial-core cases fail gracefully with actionable diagnostics.
