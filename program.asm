# A simple decrementing loop
addi $1, $0, 10       # Initialize counter in $1 to 10
addi $2, $0, 0        # Initialize loop counter in $2 to 0

loop: 
beq $1, $0, end # If $1 (counter) is 0, exit the loop
addi $2, $2, 1  # Increment loop counter $2
addi $1, $1, -1 # Decrement counter $1
j loop          # Jump back to the beginning of the loop

end:                  # End of the loop