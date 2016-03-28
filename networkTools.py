import re
import csv
import datetime
import igraph
#import networkx as nx
import sys
from statistics import mean


############ Goals: ###################
# High-level Goal
#   - Create network objects from edit data
#
# Technical Goals
#   - Work by streaming csv files instead of using SQL (i.e., no lookups)
#
# Network Types
#   - Co-editing (undirected) - A and B edit the same non-talk page within N 
#       edits/editors/seconds of each other => increment_edge(A,B)
#   - Collaboration (undirected) - network where edit_pattern = (A,B,C,...,A) =>
#       for e in edit_pattern: increment_edge(A, e) if A != e
#   - Talk (directed) - A and B edit the same talk page within N
#       edits/editors/seconds of each other OR
#       A edit's B's User_talk page => increment_edge(A,B)

# Idea space:
#   - Talk network. 
#       - Whether to connect people on Watercooler-type pages
#   - Sorting CSV will be required
#       - Sort by page, then timestamp should do the trick?


class EditNetwork(igraph.Graph):

    def __init__(self, network_type):
        if network_type =='talk':
            super().__init__(directed=True)
        else:
            super().__init__()
        self.temp_edges = []

    def avg_weight(self):
        return mean(self.es['weight'])

    def new_edges(self, from_node, to_nodes):
        self.temp_edges += [[from_node, to_node] for to_node in to_nodes]

    def make_network(self):
        nodes = set([n for e in self.temp_edges for n in e])
        nodes = sorted(nodes)
        self.add_vertices(nodes)
        self.add_edges(self.temp_edges)
        self.es['weight'] = 1

    def subgraph(self, vertices):
        v_names = [x['name'] for x in self.vs()]
        return self.induced_subgraph([v for v in vertices if v in v_names])


    def collapse_weights(self):
        self.simplify(combine_edges={"weight": "sum"})

    def betweenness(self, vertices=None, normalized=True):
        '''Takes a single vertex or list of vertices, and returns the betweenness from igraph.
        If normalized == True, then normalizes based on the constant used by ipython in R'''

        def normalize_val(x):
            # This is the normalization used by ipython in R (http://www.inside-r.org/packages/cran/igraph/docs/betweenness)
            if x == 0:
                return 0
            else:
                return x * 2 / (n*n-3*n+2)

        non_normalized_betweenness = super(EditNetwork, self).betweenness(vertices=vertices)
        n = self.vcount()
        if normalized == True:
            try:
                # If it's just a float, then normalize and return
                return normalize_val(non_normalized_betweenness)
            except TypeError:
                # Otherwise, normalize the whole list, and return
                return [normalize_val(x) for x in non_normalized_betweenness]
        else:
            return non_normalized_betweenness

    def hierarchy(self):
        '''Returns the hierarchy measure created by Krackhardt(1994) for the graph.
        This is defined as the ratio of paths in the graph which are cyclical/reciprocated.
        For a given path from v_i to v_j, the path is cyclical if there also exists a path
        from v_j to v_i.'''
        if not self.is_directed():
            raise ValueError("Hierarchy measure is only available on directed networks")
        # Get the shortest paths (this tells us whether there is a path between any two nodes)
        p = self.shortest_paths()
        # Number of hierarchical paths (non-cycles)
        h_paths = 0
        # Number of cyclical paths 
        cycles = 0
        for i in range(len(p)):
            for j in range(len(p)):
                # Check if a path exists between the nodes
                if i != j and p[i][j] != float('inf'):
                    # If it does, and the reciprocal path also exist, increment the cycle count
                    if p[j][i] < float('inf'):
                        cycles += 1
                    else:
                        # Otherwise, increment the h_paths count
                        h_paths += 1
        # Return the ratio of h_paths
        if h_paths == cycles == 0:
            return None
        return h_paths / (h_paths + cycles)

    def effective_size(self, vertex):
        ego_neighbors = self.neighbors(vertex)
        neighbor_graph = self.induced_subgraph(ego_neighbors)
        # Calculation of effective size, as described at http://www.analytictech.com/ucinet/help/hs4126.htm
        # First, get the degree of all the neighbors
        ng_degree = neighbor_graph.degree()
        # Then average the degree, and subtract it from the number of neighbors
        return len(ng_degree) - sum(ng_degree)/len(ng_degree)



def make_network(edits, network_type="coedit", edit_limit=None, editor_limit=None,
        time_limit=None, section_filter=False):
    '''
    Creates a network object based on co-edits on the same page. Takes a list of edits.
    THESE MUST BE ORDERED, by page and then by edit_time. Also takes a number
    of conditions that must exist for an edge to be created. edit_limit will create edges
    with the contributors of each of the last N edits (e.g., edit_limit = 1 means that
    only adjacent edits will result in edges.
    editor_limit is similar, but will create edges with the last N editors, while
    time_limit creates edges with all editors who have edited in the last N days.
    By default, there are no limits, and edges are created/incremented with all
    other contributors to the page.
    '''

    def add_edit(new_edit):
        '''Simple helper function that adds the current edit to the
        prev_edits list'''
        prev_edits.append(new_edit)
        # Add the metadata to the edit
        prev_edits[-1]['section'] = section
        prev_edits[-1]['edit_time'] = edit_time

    if network_type not in ['coedit', 'collaboration', 'talk']:
        raise Exception("network_type must be 'coedit', 'collaboration', or 'talk'")
    time_limit = datetime.timedelta(days = time_limit) if time_limit else None
    network = EditNetwork(network_type)
    curr_page = ''
    prev_edits = []
    for edit in edits:
        # Flag for whether this edit represents a collaboration (i.e., if
        # this editor has edited this page before, then intervening editors
        # are considered collaborators
        is_collaboration = False
        # Get the section if the section filter is True
        try:
            section = get_section_from_comment(edit['comment']) if section_filter else None
        except KeyError:
            section = None
        # Convert the timestamp to a datetime object if the time_limit is True
        edit_time = make_timestamp(edit) if time_limit else None
        coeditors = []


        # If this is a talk network, then only look at talk pages. If it's a coedit
        # or collaboration network, then ignore talk pages
        edit_is_talk_page = is_talk(edit)
        if network_type != "talk" and edit_is_talk_page:
            continue
        if network_type == "talk":
            if not edit_is_talk_page:
                continue
            else:
                # if this is a talk page, find out if it's a user talk page.
                # If it is, then create a talk edge between the editor and the
                # talk page owner
                page_owner = get_talk_page_owner(edit)
                if page_owner and page_owner != edit['editor']:
                    coeditors.append(page_owner)

        # If this is a new page, then reset stuff, and look at the next page
        # (because no edge can be created yet)
        if edit['articleid'] != curr_page:
            # Handle the situation where the first edit to a user_talk page
            # might not be recorded
            if coeditors:
                network.new_edges(edit['editor'],coeditors)
            curr_page = edit['articleid']
            prev_edits = []
            add_edit(edit)
            continue

        # If there's a limit to the number of edits to look at, then
        # get rid of any edits before that.
        if edit_limit:
            prev_edits = prev_edits[-edit_limit:]
        # Go through each of the edits in reverse order, adding edges
        # to each. Once we find one that fails the tests, only keep
        # the edits after that one (since all others would also fail, 
        # for this and subsequent edits).
        for i, prev_edit in enumerate(prev_edits[::-1]):
            if (
                    (editor_limit and len(coeditors) >= editor_limit) or
                    (time_limit and (edit_time - prev_edit['edit_time']) > time_limit)
            ):
                # Only keep the good edits
                prev_edits = prev_edits[-i:]
                break
            # If we've already seen this contributor, then we stop looking for
            # more edges, because any edges previous to
            # this one will have been captured when we looked at this contributor
            # previously.
            #
            # We don't get rid of the other prev_edits, though, b/c they might
            # be valid edges for subsequent edits
            if same_editor(edit, prev_edit):
                is_collaboration = True
                break
            else:
                # Make sure that the sections match (both will be None if
                # the section_filter is False).
                # Also, if the previous editor is already in the list, don't
                # add them again.
                if (section == prev_edit['section'] and
                        prev_edit['editor'] not in coeditors):
                    coeditors.append(prev_edit['editor'])
        # Create edges for each of the editors in the coeditor list
        if network_type != "collaboration" or is_collaboration == True:
            network.new_edges(edit['editor'],coeditors)
        # Add this edit to the prev_edits
        add_edit(edit)

    network.make_network()
    network.collapse_weights()
    return network


def make_timestamp(edit):
    return datetime.datetime.strptime(edit['date_time'], '%Y-%m-%d %H:%M:%S')

def elapsed_time(t1, t2):
    return t1 - t2


def is_talk(edit):
    '''Returns whether or not an edit was to a talk page.
    Assumes that talk pages have odd-numbered namespaces'''
    # re.match(r'[^:]*[Tt]alk:', edit['title']) - other option
    if edit['namespace'] == 'None':
        return None
    return int(edit['namespace']) % 2 == 1

def same_editor(edit1, edit2):
    return edit1['editor'] == edit2['editor']

def get_talk_page_owner(edit):
    '''Checks a talk page to see if it's a user talk page (ASSUMES THAT
    THESE ARE NAMESPACE 3). If it is a user talk
    page, then returns the user name. Otherwise, returns None'''
    if edit['namespace'] == 3:
        return re.match('[^:]+:(.*)$',edit['title']).group(1)
    else:
        return None


def get_section_from_comment(comment):
    '''Finds the section an edit was made to, based on the comment.

    ASSUMPTION:
    The first edit to a section is formatted as "Section name [dd mon yyyy]".
    Subsequent edits are "/* Section name \* Comment here".
    If there is no section name, then return None.'''
    if comment:
        a = re.match(r'\/\* (.*) \*\/.*', comment)
        if a:
            return a.group(1).rstrip()
        b = re.match(r'(.*)\[[^]]*\]$', comment)
        if b:
            return b.group(1).rstrip()
    return None

