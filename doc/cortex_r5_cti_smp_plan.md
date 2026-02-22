# Plan: CTI-based SMP run-control for Cortex-R5 in `cortex_a` target

This document outlines a practical implementation plan to add proper multi-core
(Cortex-R5) SMP halt/resume behavior to OpenOCD using CoreSight CTI/CTM, similar
in spirit to the AArch64 implementation.

## Goal

Add coordinated SMP run-control for Cortex-R4/R5 in `src/target/cortex_a.c` so
that:

- SMP halt requests can halt sibling cores via CTI channel 0.
- SMP restart/resume can restart sibling cores via CTI channel 1.
- Poll/event handling remains GDB-friendly (single visible halt event behavior)
  and robust when only some cores are examined/available.

## Existing baseline

- `cortex_a.c` currently provides only rudimentary SMP behavior by iterating over
  peers and issuing per-core operations (`cortex_a_halt_smp`, `update_halt_gdb`,
  `cortex_a_restore_smp`), without CTI-assisted synchronized cross-triggering.
- `aarch64.c` already implements CTI-assisted SMP control, including:
  - preparation helpers before coordinated halt/restart,
  - CTI channel gating and pulse generation,
  - polling logic that postpones/serializes halt events for GDB.

## Implementation plan

### 1) Add CTI configuration plumbing to `cortex_a`

1. Introduce `struct cortex_a_private_config` (or equivalent) with:
   - existing ADIv5 fields (if currently embedded elsewhere),
   - `struct arm_cti *cti`.
2. Add a `-cti` target configuration option in `cortex_a_jim_configure`, mirroring
   the `aarch64` user interface and validation behavior.
3. During `examine_first` / target init, require CTI for SMP-CTI mode and store it
   in the per-core runtime structure.

Notes:
- Keep behavior backward compatible: single-core setups without `-cti` should
  continue to work exactly as before.
- If `target->smp` is enabled and CTI is absent, return a clear runtime/config
  error when CTI-SMP path is selected.

### 2) Add runtime CTI ownership in Cortex-R/A common state

1. Add a CTI pointer in the runtime structure used by `cortex_a.c` (likely
   `struct cortex_a_common` or nested common ARMv7-A/R struct).
2. On examination, initialize CTI channel mapping used for SMP:
   - channel 0 -> halt trigger,
   - channel 1 -> restart trigger.
3. Reuse existing `arm_cti_*` APIs (`enable`, `write_reg`, `gate/ungate`,
   `pulse_channel`, `ack_events`) in the same pattern as AArch64.

### 3) Introduce CTI-based SMP halt flow

1. Add a preparation helper (analog to `aarch64_prepare_halt_smp`) that:
   - iterates over `target->smp_targets`,
   - skips unexamined or intentionally excluded peers,
   - ungates halt channel (0), gates restart channel (1),
   - records first eligible peer/core if needed for sequencing.
2. Add `cortex_a_halt_smp_cti(target, exc_target)`:
   - prepare all peers,
   - pulse channel 0 once on the selected initiator core,
   - poll all participating cores to converge state,
   - preserve existing GDB behavior by postponing non-primary halt callbacks
     until all peers are coherent.
3. Make `cortex_a_halt()` dispatch to CTI-SMP path when `target->smp` and CTI are
   both active.

### 4) Introduce CTI-based SMP restart/step-restart flow

1. Add preparation helper (analog to `aarch64_prep_restart_smp`) that:
   - handles per-core breakpoint/watchpoint restore preconditions,
   - ungates restart channel (1), gates halt channel (0),
   - acks stale halt events when required.
2. Add `cortex_a_step_restart_smp_cti()` for synchronized resume of halted group.
3. Wire existing resume/step code paths:
   - `resume` in SMP mode uses CTI synchronized restart,
   - step-over-breakpoint path keeps current semantics but uses coordinated
     restart where appropriate.

### 5) Update SMP poll/event policy for Cortex-R5

1. Extend `cortex_a_poll()` SMP logic to include an optional “postpone halt event”
   behavior similar to `aarch64_poll_smp`.
2. Ensure only one core raises the primary halt callback to GDB for a group halt,
   while sibling halted states are still updated internally.
3. Validate behavior across:
   - all cores running -> group halt,
   - mixed states (one already halted),
   - partial examination (some cores unavailable).

### 6) Config + docs + validation

1. Document `-cti` for Cortex-R4/R5 targets and expected channel usage (0 halt,
   1 resume).
2. Add/update target config examples for multi-core R5 systems (e.g., AM2434 with
   per-core CTI instances).
3. Add focused debug logs around CTI gating/pulses and fallback decisions.

## Difficult parts / risk areas

1. **State convergence and GDB notifications**
   - Existing Cortex-A/R SMP polling is simpler than AArch64. The biggest risk is
     introducing duplicate/early halt events or regressions in core-selection
     semantics for multi-core debug sessions.

2. **Heterogeneous core state at trigger time**
   - Some cores may be unexamined, in reset, or already halted. CTI-prep logic
     must tolerate this without deadlocks or indefinite waits.

3. **Channel ownership assumptions**
   - Channel 0/1 convention is taken from AArch64 implementation. Some SoCs may
     route CTI/CTM differently; design should keep mapping explicit (possibly
     future-configurable), at least with clear diagnostics when routing is wrong.

4. **Step-over-breakpoint interaction**
   - Cortex-A/R has special step-over logic. Integrating synchronized restart must
     avoid breaking one-core stepping workflows while SMP is enabled.

5. **Backward compatibility**
   - Must not regress existing non-CTI Cortex-A or single-core Cortex-R use cases.

## Open questions

1. **Scope: Cortex-R5 only vs all `cortex_a.c` users?**
   - Should CTI-SMP be enabled only for Cortex-R4/R5 IDs, or generically for all
     targets handled by `cortex_a.c` when `-cti` is present?

2. **Per-core CTI declaration model**
   - For AM2434 (4 R5 cores), do you prefer one `-cti` per target instance in TCL
     (most explicit), or an inferred naming/lookup convention?

3. **Strict vs soft dependency on CTI in SMP mode**
   - If SMP is enabled but a core lacks CTI config, should OpenOCD fail hard, or
     automatically fall back to legacy per-core halt/resume iteration?

4. **Timeout policy**
   - What timeout should be used for group-halt convergence on your XDS110 +
     AM2434 setup, and should it be configurable?

5. **Validation matrix preference**
   - Which scenarios are highest priority for your workflow?
     - group halt/resume from running,
     - halt on one core propagating to all,
     - single-step on one core while others remain halted,
     - breakpoint hit on one core while others run.

## Suggested incremental landing strategy

1. **Patch 1:** configuration/runtime CTI plumbing in `cortex_a` (no behavior
   change yet).
2. **Patch 2:** CTI group halt path + polling/event stabilization.
3. **Patch 3:** CTI group resume/step-restart integration.
4. **Patch 4:** docs + target config examples + optional tunables.

This reduces review risk and allows hardware validation on each stage with your
AM2434 setup.
