/* SPDX-License-Identifier: GPL-2.0-or-later */

volatile unsigned int cti_bkpt_counter;

void cti_breakpoint_marker(void)
{
    cti_bkpt_counter++;
    __asm__ volatile("nop");
}

void _start(void)
{
    while (1) {
        cti_breakpoint_marker();
    }
}
