from . import compiler



class State:
    """
    A state is a reference to a vertex in the graph and a set of captured groups.
    However, it's hash only dpeends on the vertex's number, not any other part of the state.
    This ensures the first possible path is always followed when it comes to group matching, as an already followed state is not overwritten.
    """
    def __init__(self,vertex,groups):
        self.vertex = vertex
        self.groups = groups

    def expand_special_edges(self,localchars):
        # returns new states that can be reached without eating a character:
        inorder = []
        existing = set()
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
                pass    
            elif typ == "end_capture":
                pass    
                
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

    def expand_special_edges(self,localchars):
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
                    neighbours = state.expand_special_edges(localchars)
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
        
class Pattern():
    def __init__(self,regexp):
        self.regexp = regexp
        self.automaton = compiler.get_automaton(regexp)
        
        
    def matches(self,s):
        # returns true or false if the string matches exaclty
        stateset = StateSet([State(self.automaton.start,{})])

        for i in range(len(s)):
            # we only read each character once
            # we start with all special edges, since these do not take a char.
            if i == 0:
                localchars = (None,s[0])
            else:
                localchars = (s[i-1],s[i])
            stateset.expand_special_edges(localchars)
            stateset.expand_char_edges(s[i])
            if not stateset.existing:
                # no more paths left
                return False
            
        # expand any last special edges that mieght reach the end
        if s:
            localchars = (s[-1],None)
        else:
            localchars = (None,None)
        stateset.expand_special_edges(localchars)

        # because the hash of a state is equivalent to the hash of the number this works:
        if self.automaton.end.number in stateset.existing:
            return True
        else:
            return False
