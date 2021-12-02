from sre_constants import *
from sre_constants import _NamedIntConstant

# new opcode that should just be ignored, used to avoid offset errors wen replacing compiled code with something smaller
last_opcode_int = int(OPCODES[-1])

new_opcodes = """
NOP
ABS_JUMP
LS_BRANCH
ABS_GROUPREF_EXISTS
ABS_REPEAT_ONE
LITERALS
""".split()

for opcode in new_opcodes:
    globals()[opcode] = _NamedIntConstant(len(OPCODES), opcode)
    OPCODES.append(globals()[opcode]) 

# if passed unicodedata is used to define numerical characters instead of isnumerical()
SRE_FLAG_STRICT_UNICODE = 512
# signifies that this is a bytes pattern, should be used internally only
SRE_FLAG_BYTE_PATTERN = 1024  

