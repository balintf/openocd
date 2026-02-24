#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Cortex-R5 CTI SMP validation harness (PLAN.md section 3.2 A-H)."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"ERROR: Required tool '{name}' was not found in PATH")


class Harness:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.openocd_proc: subprocess.Popen[str] | None = None
        self.work_dir = Path(args.work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    @property
    def openocd_log(self) -> Path:
        return Path(self.args.openocd_log)

    def start_openocd(self) -> None:
        if not self.args.openocd_cfg:
            raise SystemExit("ERROR: --openocd-cfg is required")

        cmd = [self.args.openocd_bin, *self.args.openocd_cfg, "-l", str(self.openocd_log)]
        self.openocd_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                self.ocd_tcl("targets")
                return
            except Exception:
                time.sleep(0.2)
        raise SystemExit(
            f"ERROR: OpenOCD TCL server did not come up ({self.args.tcl_host}:{self.args.tcl_port})"
        )

    def stop_openocd(self) -> None:
        if not self.openocd_proc:
            return
        if self.openocd_proc.poll() is None:
            self.openocd_proc.terminate()
            try:
                self.openocd_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.openocd_proc.send_signal(signal.SIGKILL)
                self.openocd_proc.wait(timeout=3)

    def ocd_tcl(self, cmd: str) -> str:
        nc = subprocess.run(
            ["nc", "-w", "2", self.args.tcl_host, str(self.args.tcl_port)],
            input=f"{cmd}\x1a",
            text=True,
            capture_output=True,
            check=True,
        )
        return nc.stdout.strip()

    def curstate(self, core: str) -> str:
        return self.ocd_tcl(f"{core} curstate").replace("\r", "").replace("\n", "")

    def wait_state(self, core: str, expected: str, timeout_s: float = 5.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.curstate(core) == expected:
                return
            time.sleep(0.1)
        raise SystemExit(f"ERROR: {core} did not reach state '{expected}' in {timeout_s:.1f}s")

    def assert_log_contains(self, needle: str) -> None:
        if not self.openocd_log.exists():
            raise SystemExit(f"ERROR: OpenOCD log '{self.openocd_log}' does not exist")
        txt = self.openocd_log.read_text(errors="replace")
        if needle not in txt:
            raise SystemExit(f"ERROR: OpenOCD log missing required marker: {needle}")

    def run_gdb(self, gdb_cmds: list[str], elf: str, log_name: str) -> None:
        script_body = "\n".join(
            [
                "set confirm off",
                "set pagination off",
                "set architecture arm",
                f"file {elf}",
                f"target extended-remote :{self.args.gdb_port}",
                "monitor reset halt",
                f"monitor targets {self.args.core0}",
                "monitor cortex_a smp on",
                *gdb_cmds,
                "disconnect",
                "quit",
            ]
        )

        with tempfile.NamedTemporaryFile("w", suffix=".gdb", dir=self.work_dir, delete=False) as f:
            f.write(script_body)
            gdb_script = f.name

        out = self.work_dir / log_name
        with out.open("w") as fh:
            subprocess.run([self.args.gdb_bin, "-q", "-batch", "-x", gdb_script], check=True, stdout=fh, stderr=subprocess.STDOUT)

    def scenario_a(self) -> None:
        print("[A] Bring-up and configuration checks")
        if not self.args.elf_spin:
            raise SystemExit("ERROR: --elf-spin is required for scenario A")
        self.run_gdb(["load", "monitor reset run"], self.args.elf_spin, "A.gdb.log")
        self.ocd_tcl(f"{self.args.core0} arp_examine")
        self.ocd_tcl(f"{self.args.core1} arp_examine")
        self.assert_log_contains("CTI")

    def scenario_b(self) -> None:
        print("[B] Group halt propagation")
        self.ocd_tcl(f"targets {self.args.core0}")
        self.ocd_tcl("resume")
        time.sleep(0.2)
        self.ocd_tcl("halt")
        self.wait_state(self.args.core0, "halted")
        self.wait_state(self.args.core1, "halted")

    def scenario_c(self) -> None:
        print("[C] Group synchronized resume")
        self.ocd_tcl(f"targets {self.args.core0}")
        self.ocd_tcl("halt")
        self.wait_state(self.args.core0, "halted")
        self.wait_state(self.args.core1, "halted")
        self.ocd_tcl("resume")
        self.wait_state(self.args.core0, "running")
        self.wait_state(self.args.core1, "running")

    def scenario_d(self) -> None:
        print("[D] Breakpoint hit behavior")
        if not self.args.elf_bkpt:
            raise SystemExit("ERROR: --elf-bkpt is required for scenario D")
        self.run_gdb([f"break {self.args.bkpt_symbol}", "continue", "monitor halt", "info threads"], self.args.elf_bkpt, "D.gdb.log")

    def scenario_e(self) -> None:
        print("[E] Single-step interaction")
        if not self.args.elf_step:
            raise SystemExit("ERROR: --elf-step is required for scenario E")
        self.run_gdb([f"break {self.args.step_symbol}", "continue", "x/4i $pc", "stepi", "x/4i $pc", "monitor halt"], self.args.elf_step, "E.gdb.log")

    def scenario_f(self) -> None:
        print("[F] Partial examination / unavailable core")
        self.ocd_tcl(f"{self.args.core0} arp_examine")
        self.ocd_tcl(f"targets {self.args.core0}")
        self.ocd_tcl("halt")
        self.wait_state(self.args.core0, "halted")
        print(f"INFO: verify unavailable-core diagnostics in {self.openocd_log}")

    def scenario_g(self) -> None:
        print("[G] Negative CTI configuration")
        print("INFO: run with a config that omits one -cti binding")
        self.ocd_tcl(f"targets {self.args.core0}")
        self.ocd_tcl("halt")
        self.ocd_tcl("resume")

    def scenario_h(self) -> None:
        print("[H] Timeout stress")
        print("INFO: requires platform-specific delay/clock-gating setup")
        self.ocd_tcl(f"targets {self.args.core0}")
        self.ocd_tcl("halt")
        self.ocd_tcl("resume")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cortex-R5 CTI SMP validation harness")
    p.add_argument("scenarios", nargs="*", default=list("ABCDEFGH"), help="scenario letters to run")

    p.add_argument("--openocd-bin", default=os.environ.get("OPENOCD_BIN", "openocd"))
    p.add_argument("--openocd-cfg", nargs="+", default=os.environ.get("OPENOCD_CFG", "").split())
    p.add_argument("--openocd-log", default=os.environ.get("OPENOCD_LOG", "testing/cortex-r5-cti/out/openocd.log"))
    p.add_argument("--gdb-bin", default=os.environ.get("GDB_BIN", "arm-none-eabi-gdb"))

    p.add_argument("--tcl-host", default=os.environ.get("TCL_HOST", "127.0.0.1"))
    p.add_argument("--tcl-port", type=int, default=int(os.environ.get("TCL_PORT", "6666")))
    p.add_argument("--gdb-port", type=int, default=int(os.environ.get("GDB_PORT", "3333")))

    p.add_argument("--core0", default=os.environ.get("CORE0", "r5.cpu0"))
    p.add_argument("--core1", default=os.environ.get("CORE1", "r5.cpu1"))

    p.add_argument("--elf-spin", default=os.environ.get("ELF_SPIN", ""))
    p.add_argument("--elf-bkpt", default=os.environ.get("ELF_BKPT", ""))
    p.add_argument("--elf-step", default=os.environ.get("ELF_STEP", ""))

    p.add_argument("--bkpt-symbol", default=os.environ.get("BKPT_SYMBOL", "cti_breakpoint_marker"))
    p.add_argument("--step-symbol", default=os.environ.get("STEP_SYMBOL", "cti_step_marker"))
    p.add_argument("--work-dir", default=os.environ.get("WORK_DIR", "testing/cortex-r5-cti/out"))
    return p


def main() -> int:
    args = build_arg_parser().parse_args()

    require_tool(args.openocd_bin)
    require_tool(args.gdb_bin)
    require_tool("nc")

    h = Harness(args)
    run_map = {
        "A": h.scenario_a,
        "B": h.scenario_b,
        "C": h.scenario_c,
        "D": h.scenario_d,
        "E": h.scenario_e,
        "F": h.scenario_f,
        "G": h.scenario_g,
        "H": h.scenario_h,
    }

    try:
        h.start_openocd()
        for raw in args.scenarios:
            s = raw.upper()
            if s not in run_map:
                raise SystemExit(f"ERROR: unknown scenario '{raw}'")
            run_map[s]()
    finally:
        h.stop_openocd()

    print(f"All requested scenarios completed. Logs are in {h.work_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
