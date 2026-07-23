# Bitstream handoff

You are at the end of the build: design is synthesized and implemented, timing
is closed (or the user has accepted the residual WNS), and it is time to
produce a bitstream and (optionally) program the device.

## Procedure

1. **Sanity check**: confirm the impl design exists and timing was last
   reported:

   ```
   current_project()
   report_timing(max_paths=5)
   ```

   If WNS < 0 and the user has not explicitly accepted the violation, STOP
   and ask whether to proceed. Do not generate a bitstream for a design
   that the user believes is closed but actually fails timing.

2. **Generate bitstream**:

   ```
   generate_bitstream(include_ltx=True)
   ```

   For Vivado, `include_ltx=True` produces a probes file so the user can
   debug with ILA/VIO later. The tool returns the path to the `.bit` file
   (or `.sof` for Quartus).

3. **Compute checksum**: tell the user the file size and modification time
   so they can confirm the right build went to hardware:

   ```
   exec_tcl(command="file stat <bit_path> s; puts \"$s(size) bytes, [clock format $s(mtime)]\"")
   ```

4. **Program** (only if the user asked):

   ```
   program_device(bitstream="<path>", device_index=0)
   ```

   - If `ERROR: no hw devices found`, tell the user to plug in the JTAG
     cable and check the cable drivers. Do NOT retry in a loop.

5. **Verify**: ask the user to confirm the LED / serial output they
   expected. Do not claim the design works on hardware based solely on
   `program_device` returning `ok=True` — that only confirms the FPGA was
   flashed, not that the design functions correctly.

## Handoff report

```
Bitstream handoff:
  Bitstream: <path>  (<size> bytes)
  LTX/probes: <path or "(not generated)">
  MD5:        <checksum>
  Programmed: yes (device 0, <cable>)
  Status:     bitstream flashed — please verify hardware behavior

Files to keep:
  - <bitstream>
  - <probes file if any>
  - impl log (the path reported by run_implementation)

Next steps:
  - Power-cycle / reset the board to load the new bitstream.
  - If using Vivado Hardware Manager, attach the ILA dashboard to debug.
```

## Safety rails

- Never overwrite an existing bitstream file without warning — Vivado will
  by default reuse the impl_1 output dir. If the user wants to keep the
  prior bitstream, suggest `cp <bit> <bit>.bak.YYYYMMDD` first.
- Programming the wrong device on a multi-FPGA chain can damage hardware.
  Always report the device_index used and the device's IDCODE if available.
