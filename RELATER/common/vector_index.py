# RELATER - FAISS Vector Index Module
#
# Wraps FAISS IndexHNSWFlat for GPU-accelerated approximate nearest neighbor search.
# Falls back to CPU when GPU is unavailable.

import logging

import numpy as np


def _get_faiss():
    """Import faiss, preferring GPU version."""
    try:
        import faiss
        if hasattr(faiss, 'get_num_gpus') and faiss.get_num_gpus() > 0:
            logging.info('FAISS GPU available (%d GPUs)', faiss.get_num_gpus())
        return faiss
    except ImportError:
        raise ImportError(
            'faiss-gpu (or faiss-cpu) is required for vector blocking. '
            'Install with: pip install faiss-gpu'
        )


def normalize_vectors(vectors):
    """L2-normalize each row vector in-place. Returns the same array."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    vectors /= norms
    return vectors


def build_index(embeddings, M=32, ef_construction=128, use_gpu=True):
    """Build a FAISS IndexHNSWFlat from an (N, dim) float32 array.

    Args:
        embeddings: (N, dim) float32 array, should be L2-normalized
        M: number of neighbors per layer in HNSW graph
        ef_construction: search width during index construction
        use_gpu: whether to move index to GPU

    Returns:
        faiss.Index ready for searching
    """
    faiss = _get_faiss()
    dim = embeddings.shape[1]

    # HNSW with inner product metric (equivalent to cosine after normalization)
    index = faiss.IndexHNSWFlat(dim, M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = ef_construction

    # Move to GPU if available and requested
    if use_gpu:
        try:
            if hasattr(faiss, 'get_num_gpus') and faiss.get_num_gpus() > 0:
                res = faiss.StandardGpuResources()
                index = faiss.index_cpu_to_gpu(res, 0, index)
                logging.info('FAISS index moved to GPU 0')
        except Exception as e:
            logging.warning('Failed to move FAISS index to GPU, using CPU: %s', e)

    # Add vectors
    index.add(embeddings)
    logging.info('FAISS HNSW index built: %d vectors, dim=%d, M=%d, ef_construction=%d',
                 embeddings.shape[0], dim, M, ef_construction)
    return index


def search(index, queries, k, ef_search=128):
    """Search the FAISS index.

    Args:
        index: FAISS index (may be GPU wrapper)
        queries: (Q, dim) float32 array
        k: number of nearest neighbors
        ef_search: HNSW search beam width

    Returns:
        (similarities, indices) each of shape (Q, k)
    """
    faiss = _get_faiss()

    # Set efSearch on the underlying HNSW index
    if hasattr(index, 'hnsw'):
        index.hnsw.efSearch = ef_search
    else:
        # GPU wrapper: set on the CPU index
        cpu_index = faiss.index_gpu_to_cpu(index) if hasattr(faiss, 'index_gpu_to_cpu') else index
        if hasattr(cpu_index, 'hnsw'):
            cpu_index.hnsw.efSearch = ef_search

    similarities, indices = index.search(queries, k)
    return similarities, indices


def candidate_pairs_from_search(query_keys, index_keys, similarities, indices,
                                min_cosine):
    """Convert raw FAISS search output to filtered candidate pairs.

    Args:
        query_keys: list of length Q (identifiers for query vectors)
        index_keys: list of length N (identifiers for indexed vectors)
        similarities: (Q, k) array of cosine similarities
        indices: (Q, k) array of index positions
        min_cosine: minimum cosine similarity threshold

    Returns:
        list of (query_key, index_key, cosine_sim) tuples
    """
    pairs = []
    for i in range(len(query_keys)):
        for j in range(similarities.shape[1]):
            idx = indices[i, j]
            if idx < 0:
                continue  # no more results for this query
            sim = float(similarities[i, j])
            if sim >= min_cosine:
                pairs.append((query_keys[i], index_keys[idx], sim))
    return pairs
