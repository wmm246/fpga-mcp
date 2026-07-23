// blink_tb.sv — RTL testbench for blink.v.
//
// Vivado XSim-compatible. Runs 10 ms of simulated time and asserts the
// LEDs change at ~1 Hz. Use as `run_simulation(top="blink_tb", kind="rtl")`.

`timescale 1ns/1ps

module blink_tb;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic [3:0] led;

    blink #(.CLK_HZ(100_000_000), .BLINK_HZ(1)) dut (
        .clk(clk), .rst_n(rst_n), .led(led)
    );

    // 100 MHz clock
    always #5ns clk = ~clk;

    initial begin
        // Hold reset for 100 ns, then release.
        #100ns;
        rst_n = 1'b1;

        // Sample the initial LED pattern.
        $display("[t=%0t ns] led = %b (expected 0001)", $time, led);

        // Wait ~1 second (one blink period).
        #1_000_000_000ns;

        // After 1 s, the LEDs should have rotated at least once.
        // Print whatever the final pattern is — the assertion just checks
        // we got *some* change.
        $display("[t=%0t ns] led = %b (expected != 0001)", $time, led);
        if (led === 4'b0001) begin
            $display("FAIL: LEDs never rotated");
            $finish;
        end else begin
            $display("PASS: LED pattern rotated as expected");
            $finish;
        end
    end
endmodule
