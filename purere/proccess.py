import sre_compile
import sre_parse

from .constants import *

def apply_func_ast(command_list,func):
    # Applies func recursivly to all nodes in AST
    # Func shoudl take an opcode and an argument tuple and return a list of (opcode,arg) tuples  
    state = command_list.state
    new_pattern = sre_parse.SubPattern(state)

    for opcode, args in command_list:
        # # handle recursive opcodes:
        repeating_arg = {
            MAX_REPEAT: {2},
            MIN_REPEAT: {2},
            SUBPATTERN: {3},
            ASSERT: {1},
            ASSERT_NOT: {1},
            CALL: {},
            GROUPREF_EXISTS: {1, 2},
        }
        if opcode in repeating_arg:
            argpositions = repeating_arg[opcode]
            if not argpositions:
                # argument itself is repeating_arg
                args = apply_func_ast(args,func)
            else:
                args = tuple(
                    apply_func_ast(arg,func)
                    if i in argpositions and isinstance(arg, sre_parse.SubPattern)
                    else arg
                    for i, arg in enumerate(args)
                )

        elif opcode is BRANCH:
            # handle branch seperate aas it may have many children:
            args = (args[0], [apply_func_ast(part,func) for part in args[1]])

        new_pattern.data += func(opcode,args)
    return new_pattern

def replace_repeats(opcode,args):
    if opcode in {MAX_REPEAT, MIN_REPEAT}:
        mintimes, maxtimes, torepeat = args
        if len(torepeat) == 1 and opcode is MAX_REPEAT:
            repcode = torepeat[0][0]
            if ("ANY" in str(repcode).split("_")
                or "IN" in str(repcode).split("_")
                or "RANGE" in str(repcode).split("_")
                or "LITERAL" in str(repcode).split("_")):
                # keep repeats if there is only one
                return [(opcode,args)]

        res = []
            
        if mintimes > 0:
            # unroll the minimal required parts
            res += torepeat.data * mintimes
            if maxtimes != MAXREPEAT:
                maxtimes -= mintimes
            mintimes = 0

    
        empty = sre_parse.SubPattern(torepeat.state)
         
        if maxtimes is not MAXREPEAT and maxtimes != 0:
            # we could now unroll a{0,5} as a?a?a?a?a?, but that would be a bad plan
            # this would casue a lot of backtracking, with all 2**5 combinations tried. Instead we use a series of branch operations: |a(|a(|a(|a(|a))))
            # altough funcitonally the same as |a|aa|aaa|aaaa|aaaaa, it ensures we do not keep checking the same constantly.
            # the order of branches matters for MIN/MAX
            newcode = []
            
            for number in range(maxtimes):
                subpat = sre_parse.SubPattern(torepeat.state)
                subpat.data = torepeat.data + newcode
                if opcode is MAX_REPEAT:
                    newcode = [(BRANCH, (None, [subpat, empty]))]
                else:
                    newcode = [(BRANCH, (None, [empty, subpat]))]

            res += newcode

        elif maxtimes is MAXREPEAT:
            # We need to optionally repeat forever, we rewrite this as a branch between a single go with a back jump or an empty string.
            # the jump back will be dealt with after compilation, for now we just rewrite a* as (a|)*
            empty = sre_parse.SubPattern(torepeat.state)
            newcode = sre_parse.SubPattern(torepeat.state)
            if opcode is MAX_REPEAT:
                newcode.append((BRANCH, (None, [torepeat, empty])))
            else:
                newcode.append((BRANCH, (None, [empty, torepeat])))
            res.append((opcode, (mintimes, maxtimes, newcode)))

        return res 
    else:
        # non repeat opcode
        return [(opcode, args)]

def split_repeats(opcode,args):
    if opcode in {MAX_REPEAT, MIN_REPEAT}:
        mintimes, maxtimes, torepeat = args

        if mintimes > 0 and maxtimes is MAXREPEAT:
            if maxtimes is MAXREPEAT:
                return [(opcode,(mintimes,mintimes,torepeat)),
                        (opcode,(0,MAXREPEAT,torepeat))
                        ]
            else:
                return [(opcode,(mintimes,mintimes,torepeat)),
                        (opcode,(0,maxtimes-mintimes,torepeat))
                        ]
    return [(opcode, args)]





# A single number denotes a constant length opcode
# A tuple denotes an opcode with a subpattern, the first argument is the offset of the 'skip' value in the code, and the second and third arguments give the extra bytes at the end/start that are not part of the subcode
# not submapping is done is the second and third argument are None
opcode_size = {
    "LITERAL": 2,
    LITERALS: 2,
    INFO: (None,0),
    MARK: 2,
    SUCCESS: 1,
    "GROUPREF": 2,
    "IN": (None,0), # we never need to go into a IN
    AT: 2,
    REPEAT_ONE: (2,0),
    MIN_REPEAT_ONE: (2,0),
    ABS_REPEAT_ONE: (2,0),
    REPEAT: (2,1),
    "ANY":1,
    "ASSERT": (1,0),
    FAILURE: 1,
    NEGATE: 1,
    CATEGORY: 2,
    "RANGE": 3,
    "JUMP": 2,
    CHARSET: 9,
    NOP: 1,
    LS_BRANCH:2,
}

def apply_func_code(code,func,i=0,end=None,funcargs = {}):
    res = []
    if end is None:
        end = len(code)
    # calls func on each opcode in code and allows changing it
    while i<end and i<len(code):
        opcode = code[i]
        args = substart = subend = None
        if opcode is BRANCH:
            loc = i+1
            while not code[loc] is FAILURE:
                newloc = loc + code[loc]
                res += apply_func_code(code,func,loc+1,end=newloc)
                loc = newloc
            i = loc+1                
            continue
        elif opcode is BIGCHARSET:
            numgroups = code[i+1]
            skip = 2+64+numgroups*8
            args = code[i+1:i+skip]
        elif opcode not in opcode_size:
            parts = str(opcode).split('_')
            try:
                typename = next(p for p in parts if p in opcode_size)
                skip = opcode_size[typename]
            except StopIteration:
                raise ValueError(f"Specify {opcode}")
        else:
            skip = opcode_size[opcode]
            
        if not isinstance(skip,int):
            # Complicated opcode
            startargs,endargs = skip
            if "ABS" in str(opcode):
                skip = code[i+1]+1+endargs-i
                print(i,skip)
                for c in enumerate(code):
                    print(*c)
            else:
                skip = code[i+1]+1+endargs
            
            if startargs is not None:
                args = code[i+2:i+startargs+2]+code[i+skip-endargs:i+skip]
                substart = i+startargs+2
                subend = i+skip-endargs
                res += apply_func_code(code,func,substart,subend)                
        else:
            args = code[i+1:i+skip]    
        locres = func(code,i,opcode,args,substart,subend,**funcargs)
        if locres:
            res+=locres
        i += skip
    return res

def remove_repeats(code,i,opcode,args,substart,subend):
    # Takes code compiled after replace_repeats has ben called on it
    # changes repeats { (a|)* }into branches with anegative jump and without repeat

    if opcode is REPEAT:
        repeat_type = args[2]
        assert code[substart] is BRANCH
        branch_skip = code[substart+1]  # skip of the first branch
        if repeat_type is MAX_UNTIL:
            # First of the two branches should be nonempty and end in a jump
            assert code[substart+branch_skip-1] is JUMP
            # modify argument to JUMP to point to the start of the repeat
            code[substart+branch_skip] = -(branch_skip + 4)
        else:
            # end of the repeat should be after end of second branch
            assert code[subend-3] is JUMP
            code[subend-2] = -((subend-2) - i)
        code[i : i + 4] = [NOP] * 4
        code[subend] = NOP
        
        

def combine_literals(code,i,opcode,args,substart,subend):
    if opcode is LITERAL:
        j = i
        while j < len(code) and code[j] is LITERAL:
            j += 2
        arguments = [code[pos] for pos in range(i+1, j, 2)]
        if len(arguments) > 1:
            code[i] = LITERALS
            code[i+1] = arguments
            for k in range(i + 2, j):
                code[k] = NOP



def info_len(code):
    if code[0] is INFO:
        return code[1] + 1
    else:
        return 0
                

def compile_without_repeat(regex, flags=0):
    parsed = sre_parse.parse(regex, flags)
    #parsed = apply_func_ast(parsed,split_repeats)
    parsed = apply_func_ast(parsed,replace_repeats)

    code = sre_compile._code(parsed, flags)
    apply_func_code(code,remove_repeats)
    #code = remove_repeats(code)
    return parsed.state, code
