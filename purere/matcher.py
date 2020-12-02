from . import compiler



def getnewgroups_start(groups,pos,index,name = None):
    # it is important here that we rebuild the dict since other states need to keep their dict
    if not name is None:
        newgroups = {
            'byindex': [groupset for groupset in groups['byindex']],
            'byname':  {name: groupset for name,groupset in groups['byname'].items()},
        }
        # Add to the list, do not append or use +=
        newgroups['byindex'][index] = newgroups['byindex'][index] + [(pos,None)]
        newgroups['byname'][name] = newgroups['byname'][name] + [(pos,None)]
    else:
        newgroups = {
            'byindex': [groupset for groupset in groups['byindex']],
            'byname':  groups['byname']
        }
        # Add to the list, do not append or use +=
        newgroups['byindex'][index] = newgroups['byindex'][index] + [(pos,None)]
    return newgroups

def getnewgroups_end(groups,pos,index,name = None):
    # it is important here that we rebuild the dict since other states need to keep their dict
    if not name is None:
        newgroups = {
            'byindex': [groupset for groupset in groups['byindex']],
            'byname':  {name: groupset for name,groupset in groups['byname'].items()},
        }
        # Add to the list, do not append or use +=
        last = newgroups['byindex'][index][-1]
        if not last[1] is None:
            raise Exception("Sainity check on groups failed")
        newgroups['byindex'][index] = newgroups['byindex'][index][:-1] + [(last[0],pos)]

        last = newgroups['byname'][name][-1]
        if not last[1] is None:
            raise Exception("Sainity check on groups failed")
        newgroups['name'][name] = newgroups['byname'][name][:-1] + [(last[0],pos)]
        return newgroups
    else:
        newgroups = {
            'byindex': [groupset for groupset in groups['byindex']],
            'byname':  groups['byname']
        }
        # Add to the list, do not append or use +=
        last = newgroups['byindex'][index][-1]
        if not last[1] is None:
            raise Exception("Sainity check on groups failed")
        newgroups['byindex'][index] = newgroups['byindex'][index][:-1] + [(last[0],pos)]

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
                newgroups = getnewgroups_start(self.groups,i,config['number'],config['name'])
                newstate = State(neigh,newgroups)
                
            elif typ == "end_capture":
                newgroups = getnewgroups_end(self.groups,i,config['number'],config['name'])
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
        
class Pattern():
    def __init__(self,regexp):
        self.regexp = regexp
        self.automaton = compiler.get_automaton(regexp)
        
    def matches(self,s):
        # returns true or false if the string matches exaclty
        matchedgroups = {
            'byindex':[[] for i in range(self.automaton.groups['count'])],
            'byname':{name: [] for name in self.automaton.groups['names']}
        }

        stateset = StateSet([State(self.automaton.start,matchedgroups)])

        for i in range(len(s)):
            # we only read each character once
            # we start with all special edges, since these do not take a char.

            stateset.expand_special_edges(s,i)
            stateset.expand_char_edges(s[i])
            if not stateset.existing:
                # no more paths left
                return False
            

        stateset.expand_special_edges(s,len(s))

        # because the hash of a state is equivalent to the hash of the number this works:

        for s in stateset.inorder:
            if s.vertex.number == self.automaton.end.number:
                print(s.groups)
                return True

        return False
