.data
num1:   .word 15          
num2:   .word 5          
result: .space 4         

.text

main:
    lw $t0, num1         
    lw $t1, num2          
    add $t2, $t0, $t1     
    sw $t2, result        
    sub $t3, $t0, $t1      
    sw $t3, result+4       

   