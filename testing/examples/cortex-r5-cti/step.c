/* SPDX-License-Identifier: GPL-2.0-or-later */

volatile unsigned int cti_step_counter;

void cti_step_marker(void)
{
    cti_step_counter += 1;
    cti_step_counter += 2;
    cti_step_counter += 3;
    __asm__ volatile("nop");
}

void _start(void)
{
    while (1) {
        cti_step_marker();
    }
}
