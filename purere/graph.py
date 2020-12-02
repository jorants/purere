class Vertex:
    # Vertex in the automaton
    def __init__(self,number):
        self.number = number
        # char edges eat a character
        self.char_edges = []
        # special edges is anythging that does not eat a character, for examplea free edge or ^
        # When they are walked we should also stay
        self.special_edges = []

    def add_char_edge(self,charset,vertex):
        self.char_edges.append([charset,vertex])

    def add_special_edge(self,type,vertex,config = {}):
        self.special_edges.append((type,vertex,config))

    def get_next_special(self,localchars):
        res = []
        for typ, neigh in self.special_edges:
            if typ == "free":
                res.append(neigh)
            elif typ == "start":
                if localchars[0] == None or localchars[0] == '\n':
                    res.append(neigh)
            elif typ == "end":
                if localchars[1] == None or localchars[1] == '\n':
                    res.append(neigh)
        return res
    
    def get_next_char(self,char):
        res = []
        for chars, neigh in self.char_edges:
            if char in chars:
                res.append(neigh)
        return res
            

class Automaton:
    def __init__(self,start,end,vertices):
        self.start = start
        self.end = end
        self.vertices = vertices
