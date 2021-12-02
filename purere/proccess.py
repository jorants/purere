"""
Contians functions for the proccessing of the regex AST and regex VM code to put it into a form we like
"""

import sre_compile
import sre_parse

from .constants import *

def apply_func_ast(command_list,func):
    # Applies func recursivly to all nodes in AST
    # Func should take an opcode and an argument tuple and return a list of (opcode,arg) tuples  
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

def split_repeats(opcode,args):
    # We split optional and required parts of repeats
    if opcode in {MAX_REPEAT, MIN_REPEAT}:
        mintimes, maxtimes, torepeat = args

        if mintimes > 0 and maxtimes != mintimes:
            if maxtimes is MAXREPEAT:
                return [(opcode,(mintimes,mintimes,torepeat)),
                        (opcode,(0,MAXREPEAT,torepeat))
                        ]
            else:
                return [(opcode,(mintimes,mintimes,torepeat)),
                        (opcode,(0,maxtimes-mintimes,torepeat))
                        ]
    return [(opcode, args)]

def unroll_small(opcode,args):
    # Unrolls loops with a small maximum number of repetitions
    if opcode in {MAX_REPEAT, MIN_REPEAT}:
        mintimes, maxtimes, torepeat = args
        if maxtimes <= 4 and maxtimes is not MAXREPEAT:
            if mintimes == maxtimes:
                # required small repeat unroll as a repetition
                return torepeat.data*mintimes
            elif mintimes == 0:
                # optional small repeat
                # we could now unroll a{0,5} as a?a?a?a?a?, but that would be a bad plan
                # this would casue a lot of backtracking, with all 2**5 combinations tried. Instead we use a series of branch operations: |a(|a(|a(|a(|a))))
                # altough funcitonally the same as |a|aa|aaa|aaaa|aaaaa, it ensures we do not keep checking the same part of the string constantly for the same pattern.
                # the order of branches matters for MIN/MAX
                empty = sre_parse.SubPattern(torepeat.state)
                newcode = []            
                for number in range(maxtimes):
                    subpat = sre_parse.SubPattern(torepeat.state)
                    subpat.data = torepeat.data + newcode
                    if opcode is MAX_REPEAT:
                        newcode = [(BRANCH, (None, [subpat, empty]))]
                    else:
                        newcode = [(BRANCH, (None, [empty, subpat]))]
                return newcode           
    return [(opcode, args)]


def branch_loops(opcode,args):
    # Changes loops with optionals into a branch of the content and an empty string
    # i.e., we rewrite a* as (a|)* or (|a)* depending on greedyness
    # This way there will be room to create a similair structure later on when we modify the code, and most code will already be there
    if opcode in {MAX_REPEAT, MIN_REPEAT}:
        mintimes, maxtimes, torepeat = args
        if mintimes != maxtimes: # check if this is not a fixed count loop
            empty = sre_parse.SubPattern(torepeat.state)
            newcode = sre_parse.SubPattern(torepeat.state)
            if opcode is MAX_REPEAT:
                newcode.append((BRANCH, (None, [torepeat, empty])))
            else:
                newcode.append((BRANCH, (None, [empty, torepeat])))
            return [(opcode, (mintimes, maxtimes, newcode))]
    return [(opcode, args)]

def padd_loops(opcode,args):
    # slightly anoying, but we will need more room in the code for loops to add counting opcodes so this adds a useless part to them that will get compiled into code and then written over by later processing again    
    if opcode in {MAX_REPEAT, MIN_REPEAT}:
        mintimes, maxtimes, torepeat = args
        # Leave REPEAT_ONE alone
        if not(sre_compile._simple(torepeat) and opcode is MAX_REPEAT):
            torepeat.data = [(AT,(AT_LOC_BOUNDARY)),(AT,(AT_LOC_BOUNDARY))]  +torepeat.data + [(AT,(AT_LOC_BOUNDARY)),(AT,(AT_LOC_BOUNDARY)),(AT,(AT_LOC_BOUNDARY))]
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
    REPEAT_FIXED:(1,1), 
    REPEAT_MIN_BOUNDED: (1,1), 
    REPEAT_MAX_BOUNDED:(1,1), 
    REPEAT_MIN_UNBOUNDED:(0,1), 
    REPEAT_MAX_UNBOUNDED:(0,1), 
    "ANY":1,
    "ASSERT": (1,0),
    FAILURE: 1,
    NEGATE: 1,
    CATEGORY: 2,
    "RANGE": 3,
    "JUMP": 2,
    ABS_JUMP_IF_COUNTER: 3,
    SET_COUNTER: 3,
    CHARSET: 9,
    NOP: 1,
    LS_BRANCH:2,
    ABS_GROUPREF_EXISTS: 3,
    GROUPREF_EXISTS: 3,
}

def apply_func_code(code,func,i=0,end=None,**funcargs):
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
                res += apply_func_code(code,func,i=loc+1,end=newloc,**funcargs)
                loc = newloc
            skip = loc+1-i              
        elif opcode is BIGCHARSET:
            numgroups = code[i+1]
            skip = 2+64+numgroups*8
            args = code[i+1:i+skip]
        elif opcode not in opcode_size:
            parts = str(opcode).split('_')
            try:
                typename = next(p for p in parts if p in opcode_size)
                skip = opcode_size[typename]
            except StopIteration as e:
                raise ValueError(f"Specify {opcode}") from e
        else:
            skip = opcode_size[opcode]
            
        if not isinstance(skip,int):
            # Complicated opcode
            startargs,endargs = skip
            if "ABS" in str(opcode):
                skip = code[i+1]-i
            else:
                skip = code[i+1]+1+endargs
            if startargs is not None:
                args = code[i+2:i+startargs+2]+code[i+skip-endargs:i+skip]
                substart = i+startargs+2
                subend = i+skip-endargs
                res += apply_func_code(code,func,i=substart,end=subend,**funcargs)
        else:
            args = code[i+1:i+skip]
        locres = func(code,i,opcode,args,substart,subend,**funcargs)
        if locres:
            res+=locres
        i += skip
    return res


def rename_repeats(code,i,opcode,args,substart,subend):
    if opcode is REPEAT:
        minreps,maxreps,greedy = args
        if minreps == maxreps:
            code[i] = REPEAT_FIXED
            # code[i+2] = minreps # already there
        elif maxreps is MAXREPEAT:
            #infinite loops
            if greedy is MAX_UNTIL:
                code[i] = REPEAT_MAX_UNBOUNDED
                code[i+2] = NOP
            else:
                code[i] = REPEAT_MIN_UNBOUNDED
                code[i+2] = NOP
        else:
            # bounded loops    
            if greedy is MAX_UNTIL:
                code[i] = REPEAT_MAX_BOUNDED
                code[i+2] = maxreps
            else:
                code[i] = REPEAT_MIN_BOUNDED
                code[i+2] = maxreps
        code[i+3] = NOP
        code[subend] = NOP



def rewrite_unbounded_repeats(code,i,opcode,args,substart,subend):
    if opcode is REPEAT_MAX_UNBOUNDED:
        code[i] = LS_BRANCH
        code[i+1] = [subend+1]
        code[i+2:i+8] = [NOP] *6 # we do not need space at start now
        # use space created by the extra (AT,(AT_LOC_BOUNDARY)) at the end to jump back
        code[subend-6:subend-2] = [NOP]*4
        code[subend-2:subend] = (ABS_JUMP,i)        
    elif opcode is REPEAT_MIN_UNBOUNDED:
        code[i] = LS_BRANCH
        code[i+1] = [i+4]
        code[i+2] = ABS_JUMP
        code[i+3] = subend+1
        # we do not this  need space at start now
        code[i+4:i+8] = [NOP] *4 
        code[subend-6:subend-2] = [NOP]*4
        code[subend-2:subend] = (ABS_JUMP,i)        

def rewrite_fixed_repeats(code,i,opcode,args,substart,subend,loop_counter=None):
    # changes repeats a{5} into a loop of negative conditional jumps
    if opcode is REPEAT_FIXED:
        reps = args[0]
        counter = loop_counter[0]
        loop_counter[0] +=1
        code[i:i+3] = (SET_COUNTER,counter,reps)
        code[i+4:i+8] = [NOP]*4
        jumploc = i+3
    
        code[subend-6:subend-3] = (ABS_JUMP_IF_COUNTER,counter,i+3)
        # When exiting we want to reset the counter to None
        code[subend-3:subend] = (SET_COUNTER,counter,None)

        
def rewrite_bounded_repeats(code,i,opcode,args,substart,subend,loop_counter=None):
    if opcode is REPEAT_MAX_BOUNDED:
        reps = args[0]
        counter = loop_counter[0]
        loop_counter[0] +=1
        code[i:i+3] = (SET_COUNTER,counter,reps)
        code[i+3] = LS_BRANCH
        code[i+4] = [subend-3] # still need to stop the counterin this case
        code[i+5:i+8] = [NOP] *3 # we do not need this space at start now
        code[subend-6:subend-3] = (ABS_JUMP_IF_COUNTER,counter,i+3)
        # When exiting we want to reset the counter to None
        code[subend-3:subend] = (SET_COUNTER,counter,None)
        
    elif opcode is REPEAT_MIN_BOUNDED:
        reps = args[0]
        counter = loop_counter[0]
        loop_counter[0] +=1
        code[i:i+3] = (SET_COUNTER,counter,reps)
        code[i+3] = LS_BRANCH
        code[i+4] = [i+8]
        code[i+5] = ABS_JUMP
        code[i+6] = subend-3 # still need to reset counter
        code[i+7] = NOP
        code[subend-6:subend-3] = (ABS_JUMP_IF_COUNTER,counter,i+3)
        # When exiting we want to reset the counter to None
        code[subend-3:subend] = (SET_COUNTER,counter,None)

        

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

def absolute_jump_locations(code,i,opcode,args,substart,subend):
    # changes code to have absolute jumps and branch to have a list of arguments
    # New opcodes are introduced for this with an ABS prefix
    # In addition to this branches are rewritten so all branch locations (in absolute value) are named at the start
    if opcode is JUMP:
        reljump = code[i+1]
        code[i] = ABS_JUMP
        code[i + 1] = i + 1 + reljump
        return [code[i+1]]
    elif opcode is BRANCH:
        loc = i+1
        locations = []
        while not code[loc] is FAILURE:
            newloc = loc + code[loc]
            locations.append(newloc)
            loc = newloc
        code[i] = LS_BRANCH
        code[i + 1] = locations[:-1]  # leave out the final FAILURE
        for l in locations:
            code[l] = NOP
        return code[i+1]
    elif opcode is GROUPREF_EXISTS:
        reljump = code[i+2]
        code[i] = ABS_GROUPREF_EXISTS
        code[i+2] = i + reljump +1
        return [code[i+2]]
    elif opcode is REPEAT_ONE:
        reljump = code[i+1]
        code[i] = ABS_REPEAT_ONE
        code[i+1] = i + reljump + 1
        return [code[i+1]]
    elif opcode is ABS_JUMP:
        return [code[i+1]]
    elif opcode is LS_BRANCH:
        return code[i+1]
    elif opcode is ABS_JUMP_IF_COUNTER:
        return [code[i+2]]
    elif opcode is ABS_GROUPREF_EXISTS:
        return [code[i+2]]
    elif opcode is ABS_REPEAT_ONE:
        return [code[i+1]]

def remap_jumps(code,i,opcode,args,substrat,subend,mapping={}):
    if opcode is ABS_JUMP:
        code[i + 1] = mapping[code[i + 1]]
    if opcode is ABS_JUMP_IF_COUNTER:
        code[i + 2] = mapping[code[i + 2]]
    elif opcode is LS_BRANCH:
        code[i + 1] = [mapping[v] for v in code[i + 1]]
    elif opcode is ABS_GROUPREF_EXISTS:
        code[i + 2] = mapping[code[i + 2]]
    elif opcode is ABS_REPEAT_ONE:
        code[i + 1] = mapping[code[i + 1]]
        
                

