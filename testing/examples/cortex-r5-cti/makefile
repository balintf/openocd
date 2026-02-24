# SPDX-License-Identifier: GPL-2.0-or-later

PREFIX ?= arm-none-eabi
CC := $(PREFIX)-gcc
OBJCOPY := $(PREFIX)-objcopy
SIZE := $(PREFIX)-size

CFLAGS := -mcpu=cortex-r5 -marm -g3 -O0 -ffreestanding -fno-builtin -fno-omit-frame-pointer -Wall -Wextra
LDFLAGS := -nostdlib -nostartfiles -T cti_test.ld

ELFS := spin.elf bkpt.elf step.elf
HEXS := $(ELFS:.elf=.hex)

all: $(ELFS) $(HEXS)

spin.elf: spin.c cti_test.ld
	$(CC) $(CFLAGS) $(LDFLAGS) -Wl,-Map=$(@:.elf=.map) -o $@ spin.c
	$(SIZE) $@

bkpt.elf: bkpt.c cti_test.ld
	$(CC) $(CFLAGS) $(LDFLAGS) -Wl,-Map=$(@:.elf=.map) -o $@ bkpt.c
	$(SIZE) $@

step.elf: step.c cti_test.ld
	$(CC) $(CFLAGS) $(LDFLAGS) -Wl,-Map=$(@:.elf=.map) -o $@ step.c
	$(SIZE) $@

%.hex: %.elf
	$(OBJCOPY) -O ihex $< $@

clean:
	rm -f $(ELFS) $(HEXS) *.map

.PHONY: all clean
