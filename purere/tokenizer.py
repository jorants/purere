"""
This file contains the tokenizer for regexp expressions. 
It takes a regexp string and returns a list of token with sublists representing the groups
"""
from . import charset


_START = 0
_END = 1
_OR = 2


# Repetations are denoted by tuples
_REPEAT_STAR = (0,None)
_REPEAT_PLUS = (1,None)
_OPTIONAL = (0,1)

single_char_tokens = {
    '^':_START,
    '$':_END,
    '|':_OR,
    '*':_REPEAT_STAR,
    '+':_REPEAT_PLUS,
    '?':_OPTIONAL,
}

class Group():
    """
    If capturing is None, then this group is non-capturing
    Otherwise it should be an int denoting the capture group
    """
    def __init__(self,capturing,tokens,name=None):
        self.capturing = capturing
        self.tokens = tokens
        self.name = name


def parse_group(regexp,groupcount):
    """
    returns a token (often of type Group) and the new group count
    """
    
    if regexp[0] != '?':
        # normal group, no extentions
        # parse the subexpression 
        tree,parsed,groupcount = token_tree(regexp,groupcount+1)
        token = Group(groupcount-1,tree)
        return token,parsed,groupcount
    else:
        raise ValueError("Grouptype not implemented yet")
    
def parse_general_repetition(regexp,i):
    """
    Parses {a,b} ot {a} style repetitions
    """
    # { should be followed by numbers
    for j,character in enumerate(regexp[i+1:]):
        if not character.isdigit():
            break
    num1 = int(regexp[i+1:i+j+1])
            
    if character == ",":
        # followed by a second number, repeat the above
        for k,character in enumerate(regexp[i+j+2:]):
            if not character.isdigit():
                break
        if not character == '}':
            raise ValueError("'{' was not followed by one or two integers and a closing '}'")
        num2 = int(regexp[i+j+2:i+j+k+2])
        return (num1,num2),3+j+k
    elif character == "}":
        # single number, exact matching
        return (num1,num1), 2+j
    else:
        raise ValueError("'{' was not followed by one or two integers and a closing '}'")


# outside of charsets we can have any of the escapes from inside, but the now have to be charsets (not str)
escape_lookup = {
    k: (charset.CharIndividual(v) if isinstance(v,str) else v) for k,v in charset.escape_lookup.items()
    }
    
def parse_escape(sequence):
    """
    Parses an escape sequence (excluding SLASH ) at the start of the string
    returns token and the number of parsed characters
    """
    if not sequence:
        #empty string after backslash
        raise ValueError(f"unresolved escape in regexp '{regexp}'")
    key = sequence[0]
    if key in charset.escape_lookup:
        val = escape_lookup[key]
        return val,1
    elif key == 'x':
        hexcode = regexp[i+1:i+3]
        hexcharset = charset.CharIndividual(charset.parse_hex(hexcode))
        return hexcharset,3
    elif '0'<= key <= '7':
        raise ValueError("Octal escape sequences are not implemented yet")
    else:
        raise ValueError(f"Unknown escape sequence found \\{key}")    

    
def find_end_of_charset(regexp,i):
    """
    Used to find a matching ] after a [ was read.
    We walk over the string to keep track of escaped characters and deal with SLASH ] or SLASH SLASH ].
    """
    inescape = False
    j = i+1
    while j<len(regexp):
        
        c = regexp[j]
        if not inescape:
            # We are not after a '\', interpet the character
            if c == '\\':
                inescape = True
            elif c == ']':
                break
        else:
            # we handled the next char after a '\' 
            inescape = False
        j+=1
    else:
        # no break from whileloop, so the '[' is unmatched
        raise ValueError("Unmatched '['")
    # j is now the position of the matching ']'
    return j

def token_tree(regexp,groupcount = 0):
    """
    First pass over the regexp. Converts string to tokens, and builds a tree consisting of groups and character sets.
    Returns the (sub)tree, the number of characters parsed (when ended by ')' this is not included), and the number of groups
    Recursivly calls itself for groups
    """
    result = []
    i = 0
    while i < len(regexp):
        c = regexp[i]
        if c in single_char_tokens:
            result.append(single_char_tokens[c])
            i += 1
        elif c == '{':
            token,parsed = parse_general_repetition(regexp,i)
            result.append(token)
            i+= parsed

        elif c == '}':
            # should not find the end of a character group, something wrong.
            raise ValueError("Found '}' without matching '{'")

        elif c == '(':
            # start of new group
            subregexp = regexp[i+1:]
            token,parsed,groupcount = parse_group(subregexp,groupcount)
            
            if parsed == len(subregexp):
                raise ValueError("Unmatched '('")
            if token:
                result.append(token)
            i+= 2+parsed        
        elif c == ')':
            # end of current group
            return result,i,groupcount
        elif c == ']':
            # should not find the end of a character group, something wrong.
            raise ValueError("Found ']' without matching '['")
        elif c == '[':
            # start of character group
            # we need ot find the end and pass the inbetween to charset.from_regexp
            # we seearch for ']' but need ot be carefull about escape characters
            j = find_end_of_charset(regexp,i)

            result.append(charset.from_regexp(regexp[i+1:j]))
            i = j+1
        elif c == '\\':
            token,parsed = parse_escape(regexp[i+1:])
            result.append(token)
            i+= 1+ parsed
            pass
        elif c == '.':
            result.append(charset.DOT)
            i+=1
        else:
            result.append(charset.CharIndividual(c))
            i+=1
        
    return result,i,groupcount


