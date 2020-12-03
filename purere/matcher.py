from . import compiler

def getnewgroups_start(groups,pos,index,name = None):
    # it is important here that we rebuild the dict since other states need to keep their dict
    newgroups = [groupset for groupset in groups]
    # Add to the list, do not append or use +=
    newgroups[index] = newgroups[index] + [(pos,None)]
    return newgroups

def getnewgroups_end(groups,pos,index,name = None):
    # it is important here that we rebuild the dict since other states need to keep their dict
    newgroups = [groupset for groupset in groups]
    # Add to the list, do not append or use +=
    last = newgroups[index][-1]
    if not last[1] is None:
        raise Exception("Sainity check on groups failed")
    newgroups[index] = newgroups[index][:-1] + [(last[0],pos)]
    return newgroups
        
class State:
    """
    A state is a reference to a vertex in the graph and a set of captured groups.
    However, it's hash only dpeends on the vertex's number, not any other part of the state.
    This ensures the first possible path is always followed when it comes to group matching, as an already followed state is not overwritten.
    """
    def __init__(self,vertex,groups):
        self.vertex = vertex
        self.groups = groups

    def expand_special_edges(self,s,i):
        # returns new states that can be reached without eating a character:
        inorder = []
        existing = set()
        if i == 0 and len(s) == 0:
            localchars = (None,None)
        elif i == 0:
            localchars = (None,s[0])
        elif i == len(s):
            localchars = (s[-1],None)
        else:
            localchars = (s[i-1],s[i])
            
        for typ, neigh, config in self.vertex.special_edges:
            # to avoid repetition, continue should be used when NOT creating a newstate
            # i.e. the default is to walk each special edge
            newstate = None
            if typ == "free":
                pass
            elif typ == "start":
                if not(localchars[0] == None or localchars[0] == '\n'):
                    continue
            elif typ == "end":
                if not(localchars[1] == None or localchars[1] == '\n'):
                    continue
            elif typ == "start_capture":
                newgroups = getnewgroups_start(self.groups,i,config)
                newstate = State(neigh,newgroups)
                
            elif typ == "end_capture":
                newgroups = getnewgroups_end(self.groups,i,config)
                newstate = State(neigh,newgroups)                
            else:
                 raise Exception(f"Unknown special edge type {typ}")

            if not newstate:
                newstate = State(neigh,self.groups)
            if newstate not in existing:
                inorder.append(newstate)
                existing.add(newstate)
        return inorder

    def expand_char_edges(self,char):
        # returns new states that can be reached without eating a character:
        inorder = []
        existing = set()
        for chars, neigh in self.vertex.char_edges:
            if char in chars:
                newstate = State(neigh,self.groups)
                if newstate not in existing:
                    inorder.append(newstate)
                    existing.add(newstate)
        return inorder
               
                    
    def __hash__(self):
        return hash(self.vertex.number)

    def __eq__(self,other):
        if isinstance(other,int):
            return self.vertex.number == other
        else:
            return self.vertex.number == other.vertex.number
    
class StateSet:
    """
    A stateset is a set of all currently active states.
    The order is important here, and is kept strictly when moving between the element states.
    """
    def __init__(self,states):
        self.inorder = states
        self.existing = set(states)

    def expand_special_edges(self,s,i):
        # find any reachable states without eating a character that are not in the set already.
        # here we keep states in order: if a state produces neighbours then we replace the state with itself (if needed) and its neighbours.
        
        found = set(self.inorder)
        while found:
            # handle all states present before function call, or in later round, those just found
            # we still loop over all currentstates to ensure the order
            newinorder = []
            newexisting = set()
            new_found = set()
            for state in self.inorder:
                if state not in newexisting:
                    newinorder.append(state)
                    newexisting.add(state)
                if state in found:
                    # walk to neighbours
                    neighbours = state.expand_special_edges(s,i)
                    for newstate in neighbours:
                        if newstate not in newexisting:
                            newinorder.append(newstate)
                            newexisting.add(newstate)
                            new_found.add(newstate)
            self.inorder = newinorder
            self.existing = newexisting
            found = new_found
            
    def expand_char_edges(self,char):
        newinorder = []
        newexisting = set()
        for state in self.inorder:
            neighbours = state.expand_char_edges(char)
            for newstate in neighbours:
                if newstate not in newexisting:
                    newinorder.append(newstate)
                    newexisting.add(newstate)
        self.existing = newexisting
        self.inorder = newinorder
        
    def __str__(self):
        return (" ".join(str(s.vertex.number) for s in self.inorder))


def run_automaton(automaton,string):
    """
    Runs an automaton on a string.
    Returns None if the string is rejected, returns a Match object is the string is accepted.
    """
    matchedgroups =  [[] for i in range(automaton.groups['count'])]

    stateset = StateSet([State(automaton.start,matchedgroups)])

    for i in range(len(string)):
        # we only read each character once
        # we start with all special edges, since these do not take a char.
        
        stateset.expand_special_edges(string,i)
        stateset.expand_char_edges(string[i])
        if not stateset.existing:
            # no more paths left
            return None
            

    stateset.expand_special_edges(string,len(string))
    for state in stateset.inorder:
        if state.vertex.number == automaton.end.number:
            return Match(string,state.groups,automaton.groups)
    return None
    

class Match():
    def __init__(self,string,matches,groupinfo):
        self.string = string
        self.matches = matches
        self.groupnames = groupinfo['names']

    def group(self,*args):
        if len(args) == 0:
            args = [0]
            
        if len(args) == 1:
            return self[args[0]]
        else:
            return tuple(self[a] for a in args)

    def all_group_positions(self,index):
        if isinstance(index,str):
            index = self.groupnames[index]
        return self.matches[index]
    
    def all_group_matches(self,index):
        return tuple(
            self.string[interval[0]:interval[1]]
            for interval in self.all_group_positions(index))
            
    def groups(self,default = None):
        if len(self.matches) <= 1:
            return tuple()
        if len(self.matches) == 2:
            return tuple([self.group(1)])
        else:
            indices = list(range(1,len(self.matches)))
            return tuple((r if not r is None else default) for r in self.group(*indices))
        
    def __getitem__(self,index):
        if isinstance(index,str):
            index = self.groupnames[index]
        if not self.matches[index]:
            return None
        
        interval = self.matches[index][-1]
        return self.string[interval[0]:interval[1]]
        
    
class Pattern():
    def __init__(self,regexp):
        self.fullmatch_regexp = "("+regexp+")"
        self.fullmatch_automaton = compiler.get_automaton(self.fullmatch_regexp)

        self.match_regexp = "("+regexp+").*"
        self.match_automaton = compiler.get_automaton(self.fullmatch_regexp)
        
        self.search_regexp = ".*?("+regexp+").*"
        self.search_automaton = compiler.get_automaton(self.fullmatch_regexp)

        self.findall_regexp = ".*?(?:("+regexp+").*?)*"
        self.findall_automaton = compiler.get_automaton(self.fullmatch_regexp)
        
    def fullmatch(self,s):
        return run_automaton(self.fullmatch_automaton,s)
    
    def match(self,s):
        return run_automaton(self.match_automaton,s)

    def match(self,s):
        return run_automaton(self.search_automaton,s)
        
    def findall(self,s):
        pass
        #return run_automaton(self.search_automaton,s)
