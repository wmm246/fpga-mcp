// critical_path_fixed.v — pipelined version of `critical_path.v`.
//
// The 12-deep XOR chain is split into 3 stages of 4 XORs each, with
// registers between them. Total latency becomes 3 cycles, but the
// per-cycle path delay drops to ~1 ns — easily meets 100 MHz on Artix-7.

module critical_path_fixed #(
    parameter int WIDTH = 32
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic [WIDTH-1:0] data_in,
    input  logic             valid_in,
    output logic [WIDTH-1:0] data_out,
    output logic             valid_out
);
    // Stage 1: XORs 1-4
    logic [WIDTH-1:0] x1, x2, x3, x4;
    logic [WIDTH-1:0] stage1_reg;
    logic             stage1_valid_reg;

    assign x1 = data_in ^ 32'hAAAA_AAAA;
    assign x2 = x1      ^ 32'h5555_5555;
    assign x3 = x2      ^ 32'hF0F0_F0F0;
    assign x4 = x3      ^ 32'h0F0F_0F0F;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage1_reg         <= '0;
            stage1_valid_reg   <= 1'b0;
        end else begin
            stage1_reg       <= x4;
            stage1_valid_reg <= valid_in;
        end
    end

    // Stage 2: XORs 5-8
    logic [WIDTH-1:0] x5, x6, x7, x8;
    logic [WIDTH-1:0] stage2_reg;
    logic             stage2_valid_reg;

    assign x5 = stage1_reg ^ 32'hFFFF_0000;
    assign x6 = x5         ^ 32'h0000_FFFF;
    assign x7 = x6         ^ 32'hAAAA_AAAA;
    assign x8 = x7         ^ 32'h5555_5555;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage2_reg         <= '0;
            stage2_valid_reg   <= 1'b0;
        end else begin
            stage2_reg       <= x8;
            stage2_valid_reg <= stage1_valid_reg;
        end
    end

    // Stage 3: XORs 9-12 + final output register
    logic [WIDTH-1:0] x9, x10, x11, x12;

    assign x9  = stage2_reg ^ 32'hF0F0_F0F0;
    assign x10 = x9        ^ 32'h0F0F_0F0F;
    assign x11 = x10       ^ 32'hFFFF_0000;
    assign x12 = x11       ^ 32'h0000_FFFF;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out  <= '0;
            valid_out <= 1'b0;
        end else begin
            data_out  <= x12;
            valid_out <= stage2_valid_reg;
        end
    end
endmodule
