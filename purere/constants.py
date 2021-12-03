from .stdlib.sre_constants import *
from .stdlib.sre_constants import _NamedIntConstant

new_opcodes = """
NOP
LITERALS

REPEAT_FIXED
REPEAT_MIN_BOUNDED
REPEAT_MAX_BOUNDED
REPEAT_MIN_UNBOUNDED
REPEAT_MAX_UNBOUNDED

SET_COUNTER

ABS_JUMP
ABS_JUMP_IF_COUNTER
ABS_GROUPREF_EXISTS
ABS_REPEAT_ONE
LS_BRANCH

ASSERT_SUCCESS
ASSERT_FAILURE
ABS_ASSERT_NOT

ABS_REPEAT_ANY
ABS_REPEAT_ANY_ALL
""".split()

for opcode in new_opcodes:
    globals()[opcode] = _NamedIntConstant(len(OPCODES), opcode)
    OPCODES.append(globals()[opcode]) 

# if passed unicodedata is used to define numerical characters instead of isnumerical()
SRE_FLAG_STRICT_UNICODE = 512
# signifies that this is a bytes pattern, should be used internally only
SRE_FLAG_BYTE_PATTERN = 1024  

