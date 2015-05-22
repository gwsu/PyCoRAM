reg [31:0] read_val;

initial begin
  #1000;
  wait(sim_resetn == 1);
  nclk();
  
  $display("write");
  iochannel_write_ctrl_thread_coramiochannel_0(1, 0);
  nclk();

  $display("read");
  iochannel_read_ctrl_thread_coramiochannel_0(read_val, 0);
  nclk();
  $display("value=%d", read_val);
  
  #1000;
  $finish;
end
