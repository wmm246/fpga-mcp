# critical_path.xdc — timing constraints for both versions of the design.
#
# 100 MHz clock on the input `clk` pin. Both `critical_path.v` and
# `critical_path_fixed.v` are top-level pin-compatible, so the same
# constraints file works for either.

set_property -dict { PACKAGE_PIN E3    IOSTANDARD LVCMOS33 } [get_ports clk]
create_clock -name clk_in -period 10.0 [get_ports clk]

# Treat `data_in` and `valid_in` as virtual inputs with generous input delay
# (so the tools don't try to time a non-existent input path).
set_input_delay  -clock clk_in -max 2.0 [get_ports {data_in[*]}]
set_input_delay  -clock clk_in -max 2.0 [get_ports valid_in]
set_output_delay -clock clk_in -max 2.0 [get_ports {data_out[*]}]
set_output_delay -clock clk_in -max 2.0 [get_ports valid_out]
