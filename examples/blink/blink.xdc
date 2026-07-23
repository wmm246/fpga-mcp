# blink.xdc — pin + timing constraints for the Arty A7-35 board
#
# Works on Basys3 / Nexys A7 with minor pin changes.

set_property -dict { PACKAGE_PIN E3    IOSTANDARD LVCMOS33 } [get_ports clk]
create_clock -name clk_in -period 10.0 [get_ports clk]

set_property -dict { PACKAGE_PIN C2    IOSTANDARD LVCMOS33 } [get_ports rst_n]
set_property -dict { PACKAGE_PIN H5    IOSTANDARD LVCMOS33 } [get_ports {led[0]}]
set_property -dict { PACKAGE_PIN J5    IOSTANDARD LVCMOS33 } [get_ports {led[1]}]
set_property -dict { PACKAGE_PIN T9    IOSTANDARD LVCMOS33 } [get_ports {led[2]}]
set_property -dict { PACKAGE_PIN T10   IOSTANDARD LVCMOS33 } [get_ports {led[3]}]
