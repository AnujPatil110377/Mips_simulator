
.data
N:      .word 10         # The number up to which we will sum
sum:    .word 0          # To store the final result
newline: .asciiz "\n"    # For formatting output

.text
main:
    lw $t0, N             # Load N into $t0
    li $t1, 0             # Initialize sum to 0 in $t1
    li $t2, 1             # Initialize counter to 1 in $t2

loop:
    slt $t3, $t0, $t2     # $t3 = 1 if $t0 < $t2
    bne $t3, $zero, exit  # If $t3 != 0 (i.e., N < counter), exit loop
    add $t1, $t1, $t2     # sum = sum + counter
    addi $t2, $t2, 1      # counter = counter + 1
    j loop                # Jump back to loop condition

exit:
    sw  $t1, sum          # Store the sum in memory

    # Print the sum
    li  $v0, 1            # Syscall code for print integer
    add $a0, $t1, $zero   # Move sum into $a0 for printing
    syscall               # Print the sum

    # Print newline for formatting
    li  $v0, 4            # Syscall code for print string
    la  $a0, newline      # Load address of newline into $a0
    syscall               # Print the newline

    # Exit program
    li  $v0, 10           # Syscall code for exit
    syscall