// critical_path.v — a deliberately broken design.
//
// The `combined` path is one big combinational chain (12 LUTs of XORs
// chained end-to-end) before registering. On a 100 MHz Artix-7 clock
// this path won't meet timing — WNS will be deeply negative.
//
// The fix: pipeline the chain across 3 registers. See `critical_path_fixed.v`
// for the corrected version. The MCP timing-closure flow demo uses the
// fpga-mcp `report_timing` + `set_property` + `exec_tcl` tools to:
//
//   1. Synthesize the broken design → measure WNS < 0 (failing).
//   2. Use `report_timing` to identify the failing path.
//   3. Swap in the pipelined RTL.
//   4. Re-run synth + impl → assert WNS >= 0 (closure achieved).
//
// This file is the *starting point* of the demo.

module critical_path #(
    parameter int WIDTH = 32
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic [WIDTH-1:0] data_in,
    input  logic             valid_in,
    output logic [WIDTH-1:0] data_out,
    output logic             valid_out
);
    // 12-deep XOR chain. Roughly 4-5 ns of routing + LUT delay on Artix-7.
    logic [WIDTH-1:0] x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12;

    assign x1  = data_in ^ 32'hAAAA_AAAA;
    assign x2  = x1      ^ 32'h5555_5555;
    assign x3  = x2      ^ 32'hF0F0_F0F0;
    assign x4  = x3      ^ 32'h0F0F_0F0F;
    assign x5  = x4      ^ 32'hFFFF_0000;
    assign x6  = x5      ^ 32'h0000_FFFF;
    assign x7  = x6      ^ 32'hAAAA_AAAA;
    assign x8  = x7      ^ 32'h5555_5555;
    assign x9  = x8      ^ 32'hF0F0_F0F0;
    assign x10 = x9      ^ 32'h0F0F_0F0F;
    assign x11 = x10     ^ 32'hFFFF_0000;
    assign x12 = x11     ^ 32'h0000_FFFF;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out  <= '0;
            valid_out <= 1'b0;
        end else begin
            data_out  <= x12;     // 12-deep combinational path → fails timing
            valid_out <= valid_in;
        end
    end
endmodule
