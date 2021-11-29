from sre_constants import *
from sre_constants import _NamedIntConstant

# new opcode that should just be ignored, used to avoid offset errors wen replacing compiled code with something smaller
last_opcode_int = int(OPCODES[-1])
# Ignored opcode, used to keep reletive jumps correct when removing opcodes
NOP = _NamedIntConstant(last_opcode_int + 1, "NOP")
OPCODES.append(NOP)
# Jups to a specific location instead of relatiove
ABS_JUMP = _NamedIntConstant(last_opcode_int + 2, "ABS_JUMP")
OPCODES.append(ABS_JUMP)
# Branches in one go to multiple spots instead of repeated branch instruction
LS_BRANCH = _NamedIntConstant(last_opcode_int + 3, "LS_BRANCH")
OPCODES.append(LS_BRANCH)
# ABS vesion of GROUPREF_EXISTS
ABS_GROUPREF_EXISTS = _NamedIntConstant(last_opcode_int + 3, "ABS_GROUPREF_EXISTS")
OPCODES.append(ABS_GROUPREF_EXISTS)

# Keeps track of each instance found of the group, instead of just the last one.
# Used only internally for
MARK_MANY = _NamedIntConstant(last_opcode_int + 4, "MARK_MANY")
OPCODES.append(MARK_MANY)
# Combines literal
LITERALS = _NamedIntConstant(last_opcode_int + 5, "LITERALS")
OPCODES.append(LITERALS)


SRE_FLAG_STRICT_UNICODE = 512  # if passed unicodedata is used to define numerical characters instead of isnumerical()
SRE_FLAG_BYTE_PATTERN = (
    1024  # signifies that this is a bytes pattern, should be used internally only
)