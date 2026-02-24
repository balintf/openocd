# Cortex-R5 CTI SMP validation scripts

This directory provides reusable automation for the hardware validation matrix in `PLAN.md` section **3.2 (A-H)**.

## Files

- `run_cti_validation.py`: Python orchestrator for scenarios A-H.

## Prerequisites

- OpenOCD binary from the branch under test.
- Arm none-eabi GDB.
- Netcat (`nc`).
- Firmware images matching the plan:
  - `spin.elf`
  - `bkpt.elf`
  - `step.elf`
- OpenOCD config with per-core `-cti` bindings for positive tests.

## Typical usage

```bash
python3 testing/cortex-r5-cti/run_cti_validation.py \
  --openocd-cfg -f interface/xds110.cfg -f board/ti_am2434_r5.cfg \
  --elf-spin testing/examples/cortex-r5-cti/spin.elf \
  --elf-bkpt testing/examples/cortex-r5-cti/bkpt.elf \
  --elf-step testing/examples/cortex-r5-cti/step.elf \
  A B C D E F
```

Run a single scenario:

```bash
python3 testing/cortex-r5-cti/run_cti_validation.py \
  --openocd-cfg -f interface/xds110.cfg -f board/ti_am2434_r5.cfg \
  --elf-bkpt testing/examples/cortex-r5-cti/bkpt.elf \
  D
```

## Scenario mapping to PLAN.md

- **A** Bring-up / configuration checks (`arp_examine`, CTI marker in logs).
- **B** Group halt propagation (both cores reach `halted`).
- **C** Group synchronized resume (both cores reach `running`).
- **D** Breakpoint hit behavior (cluster halt + GDB stop visibility).
- **E** Single-step interaction (step on selected core + peer state capture).
- **F** Partial examination / unavailable core (manual platform setup + log review).
- **G** Negative CTI config (rerun with one missing `-cti` mapping).
- **H** Timeout stress (manual delay/clock-gate injection).

## Notes

- Scenarios **F-H** intentionally include manual setup aspects because they are platform specific.
- Script output and logs are written to `testing/cortex-r5-cti/out` by default.
- Use `--bkpt-symbol` and `--step-symbol` if your firmware uses different labels.
