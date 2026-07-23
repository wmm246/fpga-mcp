---
name: New vendor support
about: Request support for a new FPGA vendor / toolchain
title: "[vendor] "
labels: enhancement, vendor
---

## Vendor

- Name: <!-- e.g. Gowin / Lattice Diamond / Microsemi Libero -->
- Tool binary: <!-- e.g. `gowin` / `diamond` / `libero` -->
- Tcl scripting entry point: <!-- how do you open a Tcl shell? -->

## Tool list you'd like covered

<!-- Approximate tool count + which categories. The existing catalogues are
     ~150-350 specs per vendor; you don't need to enumerate every command,
     but the categories help us scope the work. -->

- [ ] Project lifecycle (create/open/close, add sources, set top)
- [ ] Synthesis & implementation runs
- [ ] IP / block design
- [ ] Constraints (timing / physical)
- [ ] Reports (timing / utilization / DRC)
- [ ] Simulation
- [ ] Hardware manager / programmer
- [ ] Netlist queries
- [ ] Other: <!-- describe -->

## Tcl command samples

```tcl
# 3-5 representative Tcl commands from this vendor's documentation.
# e.g. how do you create a project, run synthesis, generate a bitstream.
```

## Anything else?

<!-- Link to vendor docs, sample Tcl scripts, etc. -->
