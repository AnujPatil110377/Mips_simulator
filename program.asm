.data
.text

main:
    li $a0, 5            # Load the number 5 into $a0
    jal factorial        # Call the factorial function
    add $a0, $v0, $zero  # Move the result from $v0 to $a0 for printing
    li $v0, 1            # Syscall code for print integer
    syscall              # Print the integer
    li $v0, 10           # Syscall code for exit
    syscall              # Exit the program

factorial:
    addi $sp, $sp, -8    # Create a new stack frame
    sw $ra, 4($sp)       # Save $ra on the stack
    sw $a0, 0($sp)       # Save $a0 (n) on the stack
    li $t0, 0            # Load 0 into $t0
    beq $a0, $t0, base_case  # If n == 0, branch to base_case
    addi $a0, $a0, -1    # Decrement n by 1
    jal factorial        # Recursive call to factorial(n - 1)
    lw $a0, 0($sp)       # Restore n from the stack
    mul $v0, $v0, $a0    # Multiply $v0 by n
    j end_factorial      # Jump to end_factorial to skip base_case

base_case:
    li $v0, 1            # Base case: factorial(0) = 1

end_factorial:
    lw $ra, 4($sp)       # Restore $ra from the stack
    addi $sp, $sp, 8     # Restore the stack pointer
    jr $ra               # Return to the caller