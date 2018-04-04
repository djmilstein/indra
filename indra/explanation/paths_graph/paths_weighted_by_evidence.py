import logging
import networkx as nx
from indra.explanation import paths_graph as pg
import matplotlib.pyplot as plt

logger = logging.getLogger('paths_weighted_by_evidence')

class WeightPathsByEvidence(object):
    """Weights paths from the source to the target by supporting evidence.
    Can compute the evidence for a given path and sample paths weighted by
    the supporting evidence.

    Attributes
    ----------
    graph: networkx.DiGraph
        The original graph on which we are considering paths
    cfpg: indra.explanation.paths_graph.CFPG
        The cfpg for the original graph
    evidence: dict<list<str>, int>
        A dictionary mapping direct or indirect causal relationships to the
        number of times evidence for this relationship appears.
        Ex. {('A', 'B'): 3, ('A', 'C'): 5, ('A', 'B'): 15]
    """
    def __init__(self, graph, cfpg, evidence):
        self.graph = graph
        self.cfpg = cfpg
        self.evidence = evidence
        self.source_name = cfpg.source_name
        self.target_name = cfpg.target_name

        self._compute_node_evidence()
        self._compute_node_and_children_evidence()

        debug = False
        if debug:
            self._debug_output()

    def _debug_output(self):
        if not debug:
            return
        for node in self.cfpg.graph.nodes():
            print(node)
            if node in self.node_evidence:
                print('\tNode evidence:', self.node_evidence[node])
            else:
                print('\tNo node evidence')
            if node in self.node_and_children_evidence:
                print('\tNode and children:',
                        self.node_and_children_evidence[node])
            else:
                print('\tNo node and children evidence')

    def evaluate_path(self, path):
        """Gives the number of statements supporting the given path.

        Parameters
        ----------
        path: list<str>
            A list of node names in the original graph in the order of path
            traversal

        Returns
        -------
        score: int
            The number of direct or indirect evidence statements supporting
            this path
        """
        # The path should start at the start node and end at the end node
        assert(path[0] == self.source_name)
        assert(path[len(path)-1] == self.target_name)

        path_evidence = 0

        current_node = self._cfpg_source()
        for ind in range(1, len(path)-1):
            # Note how there is no node evidence for the source or target nodes
            # so we do not iterate over those
            next_name = path[ind]
            current_node = self._cfpg_next(current_node, next_name)
            assert(current_node is not None)
            path_evidence = path_evidence + self.node_evidence[current_node]
        return path_evidence

    def _cfpg_node_history(self, cfpg_node_name):
        """Returns the set of nodes in the history."""
        fs = cfpg_node_name[2]
        history = set([v[1] for v in fs])
        history.remove(cfpg_node_name[1])  # Remove the name of the current node
        return history

    def _cfpg_penultimate(self, cfpg_node_name):
        """Returns true iff this is a node in the cfpg right before the
        goal node."""
        for s in self.cfpg.graph.successors(cfpg_node_name):
            if s[1] == self.target_name:
                return True
        return False

    def _cfpg_intermediate(self, cfpg_node_name):
        """Returns true iff this node is an intermediate node in the cfpg
        graph - not the start node nor the final node."""
        original_name = cfpg_node_name[1]
        return original_name != self.source_name and \
               original_name != self.target_name

    def _evidence_for_node_and_history(self, node, history):
        """Computes the number of statements that support some node in the
        history causing the given node.

        Attributes
        ----------
        node: str
            Name of a node in the original graph (not the cfpg)
        history: list[str]
            List of causal nodes in the original graph (not the cfpg)

        Returns
        -------
        num_evidence: int
            The number of statements providing evidence for a node in the
            history causing the effect node
        """
        num_evidence = 0
        for h in history:
            relation = (h, node)
            if relation in self.evidence:
                num_evidence = num_evidence + self.evidence[relation]
        return num_evidence

    def _cfpg_source(self):
        """Finds the node in the cfpg corresponding to the source node.
        There should only be one."""
        source_nodes = []
        for node in self.cfpg.graph.nodes():
            if node[1] == self.source_name:
                source_nodes.append(node)
        assert(len(source_nodes) == 1)
        return source_nodes[0]

    def _cfpg_target(self):
        """Finds the node in the cfpg corresponding to the target node.
        There should only be one."""
        target_nodes = []
        for node in self.cfpg.graph.nodes():
            if node[1] == self.target_name:
                target_nodes.append(node)
        assert(len(target_nodes) == 1)
        return target_nodes[0]

    def _cfpg_next(self, cfpg_current, original_next):
        """Finds the node in the cfpg graph corresponding to moving to
        a new node, with name specified in the original graph.

        Parameters
        ----------
        cfpg_start: str
            The name of the node to move from (in the cfpg graph)
        original_next: str
            The name of the next node to go to (name in the original graph)

        Returns
        -------
        cfpg_next: str
            The node name in the cfpg graph corresponding to moving to
            the node named original_next in the original graph. None if there
            is no such node in the cfpg graph.
        """
        node_cfpg = []
        for node in self.cfpg.graph.successors(cfpg_current):
            if node[1] == original_next:
                node_cfpg.append(node)

        # There should be at most one way to move to a new node with
        # a given name
        assert(len(node_cfpg) <= 1)
        if len(node_cfpg) == 1:
            return node_cfpg[0]
        else:
            return None
 
    def _compute_node_evidence(self):
        """Computes the supporting evidence for each node of the cfpg."""
        self.node_evidence = {}
        for node in self.cfpg.graph.nodes():
            if self._cfpg_intermediate(node):
                history = self._cfpg_node_history(node)

                num_evidence = self._evidence_for_node_and_history(node[1],
                                                                   history)

                # cfpg structures do not include the history set for the final
                # node, so include evidence for the final node within the node
                # evidence for the penulatimate node.
                if self._cfpg_penultimate(node):
                    # History of getting to target node
                    extended_history = set(history)
                    extended_history.add(node[1])
                    num_evidence = num_evidence + \
                                   self._evidence_for_node_and_history(
                                           self.target_name, extended_history)
                self.node_evidence[node] = num_evidence


    def _compute_node_and_children_evidence(self):
        """Computes evidence for a node and all of its children."""
        self.node_and_children_evidence = {}
        target = self._cfpg_target()
        process_these_next = self.cfpg.graph.predecessors(target)

        while len(process_these_next) > 0:
            # Put the next set of nodes to process in the queue
            queue = set(process_these_next)
            process_these_next = []

            for node in queue:
                if node[1] == self.source_name:
                    num_evidence = 0
                else:
                    num_evidence = self.node_evidence[node]
                for child in self.cfpg.graph.successors(node):
                    if child != target:
                        assert(child in self.node_and_children_evidence)
                        num_evidence = num_evidence + \
                                       self.node_and_children_evidence[child]
                self.node_and_children_evidence[node] = num_evidence

                process_these_next.extend(self.cfpg.graph.predecessors(node))

if __name__ == '__main__':
    g_orig = nx.DiGraph()
    g_orig.add_edges_from((
                              ('A', 'B2'),
                              ('B2', 'C1'),
                              ('B2', 'C2'),
                              ('C2', 'D1'),
                              
                              ('A', 'B1'),
                              ('B1', 'C1'),
                              ('C1', 'D1'),

                              ('A', 'B3'),
                              ('B3', 'C3'),
                              ('C3', 'D1')
                            ))
    main_path = ('A', 'B1', 'C1', 'D1')
    secondary_path = ('A', 'B2', 'C1', 'D1')
    source = 'A'
    target = 'D1'
    length = 3

    cfpg = pg.CFPG.from_graph(g_orig, source, target, length)

    evidence = { ('A', 'B2') : 100,
                 ('B2', 'C2') : 2,
                 ('A', 'C2') : 2,
                 ('A', 'B1') : 1500,
                 ('A', 'C1') : 500,
                 ('B1', 'C1') : 500,
                 ('B2', 'C1') : 500,
                 ('A', 'B3') : 5,
                 ('A', 'C3') : 5,
                 ('A', 'D1') : 500,
                 ('C2', 'D1') : 5,
                 ('C1', 'D1') : 500,
                 ('C3', 'D1') : 5
              }

    weightedPaths = WeightPathsByEvidence(g_orig, cfpg, evidence)
    node0 = cfpg.graph.nodes()[0]

    paths = cfpg.enumerate_paths()
    for path in paths:
        print(path)
        print(weightedPaths.evaluate_path(path))
