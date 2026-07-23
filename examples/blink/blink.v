// blink.v — a 1 Hz LED blinker for Artix-7 (xc7a35tcpg236-1)
//
// Drives 4 LEDs with a 1-bit counter at ~1 Hz on a 100 MHz clock.
// Tiny enough to fit any Artix-7 board (Arty, Basys3, Nexys A7, …).

module blink #(
    parameter int CLK_HZ   = 100_000_000,  // 100 MHz reference
    parameter int BLINK_HZ = 1             // desired blink rate
) (
    input  logic clk,
    input  logic rst_n,           // active-low, debounced
    output logic [3:0] led
);
    localparam int DIV = CLK_HZ / (2 * BLINK_HZ);

    logic [31:0] counter;
    logic        tick;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 32'd0;
            tick    <= 1'b0;
        end else begin
            if (counter == DIV-1) begin
                counter <= 32'd0;
                tick    <= 1'b1;
            end else begin
                counter <= counter + 32'd1;
                tick    <= 1'b0;
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            led <= 4'b0001;
        end else if (tick) begin
            led <= {led[2:0], led[3]};   // rotate left
        end
    end
endmodule
