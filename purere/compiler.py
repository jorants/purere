"""
Second step in compilation, takes a tokentree and compiles it to an AST.
AST nodes can compile themselfs into an automaton
"""
from . import charset
from . import tokenizer
from .graph import Vertex,Automaton


class AST:
    # each AST node has a simplify and an automaton function
    def simplify(self):
        return self
    
class Alternatives(AST):
    def __init__(self,alternatives):
        self.alternatives = alternatives

    def __str__(self,indent = 0):
        res = [" "*indent+"Alternatives:"]+[a.__str__(indent=indent+1) for a in self.alternatives]
        return "\n".join(res)

    def simplify(self):
        self.alternatives = [a.simplify() for a in self.alternatives]
        newalternatives = []
        for a in self.alternatives:
            if isinstance(a,Alternatives):
                newalternatives += a.alternatives
            else:
                newalternatives.append(a)
        self.alternatives = newalternatives
        return self

    def automaton(self,number):
        start = Vertex(number)
        end = Vertex(number+1)
        number += 2

        vertices = [start,end]
        for alt in self.alternatives:
            auto = alt.automaton(number)
            number+= len(auto.vertices)
            start.add_special_edge("free",auto.start)
            auto.end.add_special_edge("free",auto.end)
            vertices += auto.vertices
            
        return  Automaton(start,end,vertices)
    

class Optional(AST):
    def __init__(self,value,greedy=False):
        self.value = value
        self.greedy = greedy

    def __str__(self,indent = 0):
        return " "*indent+f"Optional:\n"+self.value.__str__(indent=indent+1)

    def automaton(self,number):       
        start = Vertex(number)
        end = Vertex(number+1)
        repauto = self.value.automaton(number+2)
        if self.greedy:
            # first try repauto
            start.add_special_edge("free",repauto.start)
            start.add_special_edge("free",end)
        else:
            start.add_special_edge("free",end)
            start.add_special_edge("free",repauto.start)
            
        repauto.end.add_special_edge("free",end)
        return Automaton(start,end,[start,end]+repauto.vertices)
    
class Unlimited(AST):
    def __init__(self,value,greedy=False):
        self.value = value
        self.greedy = greedy
        
    def __str__(self,indent = 0):
        return " "*indent+f"Unlimited:\n"+self.value.__str__(indent=indent+1)

    def automaton(self,number):       
        start = Vertex(number)
        end = Vertex(number+1)
        repauto = self.value.automaton(number+2)
        if self.greedy:
            # first try a repeat
            start.add_special_edge("free",repauto.start)
            start.add_special_edge("free",end)
        else:
            start.add_special_edge("free",end)
            start.add_special_edge("free",repauto.start)
            
        repauto.end.add_special_edge("free",start)
        return Automaton(start,end,[start,end]+repauto.vertices)

    
class Repeat(AST):
    def __init__(self,value,lower,upper,greedy = False):
        self.value = value
        self.lower = lower
        self.upper = upper
        self.greedy = greedy
        if not 0 <= lower:
            raise ValueError("Minimum number of repetations should be at least 0")
        if upper and not (lower<=upper):
            raise ValueError("Max number of repetations should be at least Min number")
        
    def __str__(self,indent = 0):
        return " "*indent+f"Repeat({self.lower},{self.upper}):\n"+self.value.__str__(indent=indent+1)

    def simplify(self):
        self.value = self.value.simplify()
        if self.lower and self.lower > 0:
            if self.upper == None:
                newnode = Concat(
                    [self.value]*self.lower
                    +[Unlimited(self.value,greedy=self.greedy)])
            else:
                newnode = Concat(
                    [self.value]*self.lower
                    +[Optional(self.value,greedy=self.greedy)]*(self.upper-self.lower))
        newnode = newnode.simplify()
        return newnode

    def automaton(self):
        raise Exception("Repeat should be simplified before generating automaton")
        
class Concat(AST):
    def __init__(self,parts):
        self.parts = parts

    def __str__(self,indent = 0):
        res = [" "*indent+"Concat:"]+[p.__str__(indent=indent+1) for p in self.parts]
        return "\n".join(res)

    def simplify(self):
        self.parts = [p.simplify() for p in self.parts]
        newparts = []
        for p in self.parts:
            if isinstance(p,Concat):
                newparts += p.parts
            else:
                newparts.append(p)
        self.parts = newparts
        return self

    def automaton(self,number):
        last = None
        autos = []
        for part in self.parts:
            auto = part.automaton(number)
            number+= len(auto.vertices)
            if last:
                last.end.add_special_edge("free",auto.start)
            autos.append(auto)
            last = auto
        
            
        start = autos[0].start
        end = autos[-1].end
        vertices = [v for a in autos for v in a.vertices]
        return  Automaton(start,end,vertices)
    
        
class InputCheck(AST):
    # nodes that depend on the input for their edges.
    pass

class Start(InputCheck):
    def __str__(self,indent = 0):
        return " "*indent+"Start"

    def automaton(self,number):
        start = Vertex(number)
        end = Vertex(number+1)
        start.add_special_edge("start",end)
        auto = Automaton(start,end,[start,end])
        return auto    

    
class End(InputCheck):
    def __str__(self,indent = 0):
        return " "*indent+"End"

    def automaton(self,number):
        start = Vertex(number)
        end = Vertex(number+1)
        start.add_special_edge("end",end)
        auto = Automaton(start,end,[start,end])
        return auto    
    
class Empty(InputCheck):
    # the emptry regexp, does nothing
    def __str__(self,indent = 0):
        return " "*indent+"Empty"

    def automaton(self,number):
        start = Vertex(number)
        auto = Automaton(start,start,[start])
        return auto
    
class SingleCharacter(InputCheck):
    def __init__(self,charset):
        self.charset = charset

    def __str__(self,indent = 0):
        res = " "*indent+"Charset:\n"+self.charset.__str__(indent=indent+1)
        return res

    def automaton(self,number):
        start = Vertex(number)
        end = Vertex(number+1)
        start.add_char_edge(self.charset,end)
        auto = Automaton(start,end,[start,end])
        return auto

class CapturingGroup(AST):
    def __init__(self,number,value,name = None):
        self.number = number
        self.value = value
        self.name = name

    def __str__(self,indent = 0):
        return " "*indent+f"CapturingGroup({self.number}{','+self.name if self.name else ''}):\n"+self.value.__str__(indent=indent+1)

    def simplify(self):
        # no simplifications, just pass it on
        self.value = self.value.simplify()
        return self
    
    def automaton(self,number):
        start = Vertex(number)
        end = Vertex(number+1)
        subauto = self.value.automaton(number+2)
        start.add_special_edge("start_capture",subauto.start,config = {'number':self.number,'name':self.name})
        subauto.end.add_special_edge("end_capture",end,config = {'number':self.number,'name':self.name})
        return  Automaton(start,end,[start,end]+subauto.vertices)
    
    
    
    
def ast_for_tokentree(tree):
    """
    Compiles a tokentree to an ast.
    It recurses when it encounters groups.
    Within a group it relies heavily on the fact that each group is a set of 0 or more alternatives
    Each alternative is the concatination of 0 or more parts
    Each part is either a character class, a group, a repetation or a special lookup.
    """
    alternatives = []
    currentparts = []
    for token in tree:
        if isinstance(token,charset.Charset):
            currentparts.append(SingleCharacter(token))
        elif isinstance(token,tokenizer.Group):
            subast = ast_for_tokentree(token.tokens)
            if token.capturing is None:
                # non capturing groups can just be added as tree
                currentparts.append(subast)
            else:
                # capturing group
                group = CapturingGroup(token.capturing,subast,token.name)
                currentparts.append(group)                
        elif token == tokenizer._START:
            currentparts.append(Start())
        elif token == tokenizer._END:
            currentparts.append(End())
        elif isinstance(token,tuple):
            if not currentparts:
                raise ValueError("Repetition operator in regexp without something to repeat")
            torepeat = currentparts.pop()
            if isinstance(torepeat,Start) or isinstance(torepeat,End):
                # TODO: is this needed?
                raise ValueError("Repetition operator can not be aplied to ^ or $")
            if isinstance(torepeat,Repeat):
                if token == tokenizer._OPTINAL and not torepeat.greedy:
                    # The ? denoted a non greedy repetition
                    torepeat.greedy = True
                    currentparts.append(torepeat)
                    continue
                else:
                    raise ValueError("Multiple repeats")
            currentparts.append(Repeat(torepeat,*token))
        elif token == tokenizer._OR:
            # Optimize so that an empty or single item alternative is not concatinated.
            # When changed, also change below
            if len(currentparts) == 0:
                alternatives.append(Empty())
            elif len(currentparts) == 1:
                alternatives.append(currentparts[0])
            else:
                current = Concat(currentparts)
                alternatives.append(current)
            currentparts = []

    # handle any remaining in this alternative
    if len(currentparts) == 0:
        alternatives.append(Empty())
    elif len(currentparts) == 1:
        alternatives.append(currentparts[0])
    else:
        current = Concat(currentparts)
        alternatives.append(current)            

    # optimzation to not add any single alternatives
    if len(alternatives) == 1:
        return alternatives[0]
    else:
        return Alternatives(alternatives)
        

def get_ast(regexp):
    """
    Creates an AST from a regexp by first converting to a tree of groups and tokens, and then applying the Shunting-yard algorithm
    """        
    tree,length,groupcount = tokenizer.token_tree(regexp)
    if length != len(regexp):
        raise ValueError("Found ')' without matching '('")
    return ast_for_tokentree(tree)


def get_automaton(regexp):
    tree = get_ast(regexp)
    print(tree)
    tree = tree.simplify()
    return tree.automaton(0)

