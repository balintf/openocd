/* SPDX-License-Identifier: GPL-2.0-or-later */

volatile unsigned int core0_heartbeat;
volatile unsigned int core1_heartbeat;

void _start(void)
{
    while (1) {
        core0_heartbeat++;
        core1_heartbeat += 2;
        __asm__ volatile("nop");
    }
}
