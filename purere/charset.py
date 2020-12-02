"""
This file contains the definitions for character sets, which form character classes.
All character sets should implement an __contains__ operator that checks a single char for membership. 

This file also contains a hand written tokenizer and parser for character clas regexp defenitions.
"""


class Charset():
    # common parrent, should not be used dirctly
    def __contains__(self,char):
        if len(char) != 1:
            raise ValueError(f"Can only check memberchip of charachter set for a single char, not '{char}'")
        if hasattr(super(),"__contains__"):
            return super().__contains__(char)
        
class CharIndividual(Charset,set):
    # set of individual characters, simply extends the python set
    def __str__(self,indent=0):
        return " "*indent+"".join(self)


class CharRange(Charset):
    def __init__(self,lower,upper):
        self.lower = lower
        self.upper = upper

    def __contains__(self,char):
        super().__contains__(char)

        return self.lower <= char <= self.upper

    def __str__(self,indent=0):
        return " "*indent+self.lower+"-"+self.upper

    
class CharCombination(Charset):
    def __init__(self,sets, negate  = False):
        self.sets = sets
        self.negate = bool(negate)
        
    def __contains__(self,char):
        super().__contains__(char)
        # the != implements the XOR, i.e., flip the answer when negate is true
        return self.negate != any(char in s for s in self.sets)
    

    def __str__(self,indent = 0):
        res = [" "*indent+"Combination({'negated' if self.negate}):"]+[s.__str__(indent=indent+1) for s in self.sets]
        return "\n".join(res)

    
    
DOT = CharCombination(
    [CharIndividual('\n')],
    negate = True)

DIGIT = CharCombination(
    [CharRange('0','9')],
    negate = False)

NOTDIGIT = CharCombination(
    [CharRange('0','9')],
    negate = True)

# TODO: fix for unicode 
WS = CharCombination(
    [CharIndividual(" \t\n\r\f\v")],
    negate = False)
 
NOTWS = CharCombination(
    [CharIndividual(" \t\n\r\f\v")],
    negate = True)

WORD = CharCombination(
    [CharRange('a','z'),
     CharRange('A','Z'),
     CharRange('0','9'),
     CharIndividual('_')],
    negate = False)
    
NOTWORD = CharCombination(
    [CharRange('a','z'),
     CharRange('A','Z'),
     CharRange('0','9'),
     CharIndividual('_')],
    negate = True)

special_sets_lookup = {
    'd':DIGIT,
    'D':NOTDIGIT,
    's':WS,
    'S':NOTWS,
    'w':WORD,
    'W':NOTWORD,
}

simple_char_escape_lookup = { c:c for c in ".^$*+?{}[]|()"} 
special_char_escape_lookup = {repr(c)[2:-1]:c for c in "\'\"\\\n\r\t\b\f\a\v"}
escape_lookup = {**special_sets_lookup,** simple_char_escape_lookup , ** special_char_escape_lookup}

_NOT = 0
_TILL = 1

def parse_hex(hexcode):
    hexdigits = "0123456789abcdef"
    hexcode = hexcode.lower()
    if len(hexcode) != 2 or not (hexcode[0] in hexdigits and hexcode[1] in hexdigits):
        raise ValueError(f"{hexcode} is not a valid hexcode")
    digit1, digit2 = hexcode
    if digit1.isdigit():
        digit1 = int(digit1)
    else:
        digit1 = 10+ ord(digit1) - ord('a')
    if digit2.isdigit():
        digit2 = int(digit2)
    else:
        digit2 = 10+ ord(digit2) - ord('a')
    return chr(digit1*16+digit2)

def tokenize(regexp):
    """
    Takes a character set definition from a regexp and transforms it into a list of tokens.
    The string should be the litteral part beteen the '[' and ']' characters
    """
    result = []
    i = 0
    while i < len(regexp):
        c = regexp[i]
        if i == 0 and c == '^':
            result.append(_NOT)
            i += 1
        elif c == '-':
            result.append(_TILL)
            i+=1
        elif c == '\\':
            # escape sequence
            if i+1 >= len(regexp):
                raise ValueError(f"Character set '{regexp}' ends with an unresolved escape")
            key = regexp[i+1]
            if key in escape_lookup:
                result.append(escape_lookup[key])
                i+=2
            elif key == 'x':
                hexcode = regexp[i+1:i+3]
                result.append(parse_hex(hexcode))
                i += 4
            elif '0'<= key <= '7':
                raise ValueError("Octal escape sequences are not implemented yet")
            else:
                raise ValueError(f"Unknown escape sequence found \\{key}")
        elif c == '.':
            result.append(DOT)
            i+=1
        else:
            result.append(c)
            i+=1
        
    return result
                
        
def from_regexp(regexp):
    """
    Takes a character set definition from a regexp and transforms it into a charset object.
    The string should be the litteral part beteen the '[' and ']' characters
    """
    tokens = tokenize(regexp)
    parts = []
    seperate_chars = []
    negate = False
    i = 0
    while i < len(tokens):
        # we eat all the tokens
        cur = tokens[i]
        if cur == _NOT:
            negate = True
            i+=1
        elif isinstance(cur,Charset):
            parts.append(cur)
            i+=1
        elif cur == _TILL:
            raise ValueError("'-' should be between two characters")

        # remaining are normal characters
        elif i < len(tokens)-2 and tokens[i+1] == _TILL and isinstance(tokens[i+2],str):
            # range
            parts.append(CharRange(cur,tokens[i+2]))
            i += 3
            continue
        else:
            seperate_chars.append(cur)
            i+=1
    parts.append(CharIndividual(seperate_chars))
    if not parts:
        raise ValueError("Empty character set is not allowed")
    elif not negate and len(parts) == 1:
        return parts[0]
    else:
        return CharCombination(parts,negate = negate)
