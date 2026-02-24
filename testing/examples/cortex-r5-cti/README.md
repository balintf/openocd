# Cortex-R5 CTI validation firmware examples

Small bare-metal binaries used by `testing/cortex-r5-cti/run_cti_validation.py`.

## Outputs

- `spin.elf`: infinite loop heartbeat workload for bring-up/halt/resume checks.
- `bkpt.elf`: repeatedly calls `cti_breakpoint_marker` for breakpoint-stop tests.
- `step.elf`: repeatedly calls `cti_step_marker` for single-step validation.

## Build

```bash
cd testing/examples/cortex-r5-cti
make
```

Use the resulting ELF paths with `--elf-spin`, `--elf-bkpt`, and `--elf-step`.
