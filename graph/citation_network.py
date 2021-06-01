from typing import Dict
import networkx as nx
import numpy as np
from numpy.typing import ArrayLike
from sklearn.cluster import DBSCAN, SpectralClustering
from scipy.linalg import eigh
from db.db_models import db, Citation
import graph.case_similarity

MAX_DEPTH = 122  # To normalize lowest edge weight to 1


class CitationNetwork:
    network: nx.Graph
    similarity: graph.case_similarity.CitationNetworkSimilarity

    def __init__(self, directed=False):
        self.network = self.construct_network(directed)
        self.similarity = graph.case_similarity.CitationNetworkSimilarity(self.network)

    @staticmethod
    def construct_network(directed=False):
        if directed:
            citation_network = nx.DiGraph()
        else:
            citation_network = nx.Graph()
        db.connect()
        citations = [(c.citing_opinion, c.cited_opinion, 1 / c.depth) for c in Citation.select()]
        db.close()
        citation_network.add_weighted_edges_from(citations)
        return citation_network

    def dbscan_cluster(self, opinion_ids: set, eps=0.94) -> Dict[int, set]:
        sgraph = self.similarity.internal_similarity(opinion_ids)
        slaplacian = nx.laplacian_matrix(sgraph).toarray()
        slaplacian += 1
        sdist = slaplacian * (1 - np.identity(slaplacian.shape[0]))
        labels = DBSCAN(eps=eps, min_samples=1, metric="precomputed") \
            .fit(sdist) \
            .labels_
        output = {}
        for c, l in zip(opinion_ids, labels):
            if not l in output:
                output[l] = set()
            output[l].add(c)
        return output

    def spectral_cluster(self, opinion_ids: set, num_clusters=None):
        graph = self.similarity.internal_similarity(opinion_ids)
        affinity_mat = nx.to_numpy_matrix(graph)
        if num_clusters is None:
            num_clusters = self.optimal_num_clusters(affinity_mat)

        labels = SpectralClustering(num_clusters, affinity='precomputed', assign_labels='discretize').fit(affinity_mat).labels_
        output = {}
        for c, l in zip(opinion_ids, labels):
            if l not in output:
                output[l] = set()
            output[l].add(c)
        return output

    def optimal_num_clusters(self, affinity_mat: ArrayLike) -> int:
        """https://papers.nips.cc/paper/2004/file/40173ea48d9567f1f393b20c855bb40b-Paper.pdf
        See Section 3.1 of the above paper for discussion of this technique.
        """
        largest_drop, largest_drop_index = 0, 0
        eigenvalues = sorted(eigh(affinity_mat)[0], reverse=True)
        for i in range(1, len(eigenvalues)):
            if (curr_drop := eigenvalues[i - 1] - eigenvalues[i]) > largest_drop:
                largest_drop, largest_drop_index = curr_drop, i
            if eigenvalues[i] < 0.2:  # Impose a baseline filter to avoid over-partitioning cases
                break
        return largest_drop_index or 1

