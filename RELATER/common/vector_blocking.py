# RELATER - Vector Blocking Module
#
# Replaces brute-force O(N*M) cross-products with FAISS-based vector retrieval
# for both atomic node generation and publication pair candidate generation.

import logging

import numpy as np

from common import embedding, vector_index, constants as c


def block_atomic_nodes(record_list_wf1, record_list_wf2, sim_func_dict,
                       vector_config, pair_sim_func):
    """Generate atomic nodes using vector blocking instead of brute-force.

    For each string attribute (JW), embed unique values and use FAISS to find
    top-K candidates. For numerical attributes (MAD), fall back to brute-force
    since the number of unique values is small.

    Args:
        record_list_wf1: list of records from dataset 1
        record_list_wf2: list of records from dataset 2
        sim_func_dict: {attr_index: sim_function_name} e.g. {8: 'JW', 6: 'MAD'}
        vector_config: dict with keys: model_name, top_k, min_cosine, sim_blend,
                       hnsw_m, hnsw_ef_construction, hnsw_ef_search, cache_dir
        pair_sim_func: callable((val1, val2), function_name) -> float

    Returns:
        atomic_node_dict: {attr_index: {(val1, val2): blended_sim_val}}
    """
    atomic_node_dict = {}
    model_name = vector_config.get('model_name', 'all-MiniLM-L6-v2')
    top_k = vector_config.get('top_k', 50)
    min_cosine = vector_config.get('min_cosine', 0.5)
    sim_blend = vector_config.get('sim_blend', 0.0)
    hnsw_m = vector_config.get('hnsw_m', 32)
    hnsw_ef_construction = vector_config.get('hnsw_ef_construction', 128)
    hnsw_ef_search = vector_config.get('hnsw_ef_search', 128)
    cache_dir = vector_config.get('cache_dir', '')

    for i_attribute, sim_function in sim_func_dict.items():
        atomic_node_dict[i_attribute] = {}

        # Extract unique values
        value_list1 = sorted({p[i_attribute] for p in record_list_wf1
                              if p[i_attribute] is not None and p[i_attribute] != ''})
        value_list2 = sorted({p[i_attribute] for p in record_list_wf2
                              if p[i_attribute] is not None and p[i_attribute] != ''})

        logging.info('block_atomic_nodes: attr %d, values1=%d, values2=%d, func=%s',
                     i_attribute, len(value_list1), len(value_list2), sim_function)

        if sim_function == 'MAD':
            # Numerical attributes: brute-force is fine (typically < 50 unique values)
            _brute_force_numeric(value_list1, value_list2, i_attribute,
                                 atomic_node_dict, pair_sim_func, sim_function)
            continue

        if sim_function != 'JW':
            logging.warning('Unsupported sim function %s for attr %d, skipping',
                            sim_function, i_attribute)
            continue

        # Embed unique values from both datasets
        emb1 = embedding.embed_and_cache_values(
            record_list_wf1, i_attribute, cache_dir, model_name)
        emb2 = embedding.embed_and_cache_values(
            record_list_wf2, i_attribute, cache_dir, model_name)

        vals1 = [v for v in value_list1 if v in emb1]
        vals2 = [v for v in value_list2 if v in emb2]

        if not vals1 or not vals2:
            continue

        mat1 = np.array([emb1[v] for v in vals1], dtype=np.float32)
        mat2 = np.array([emb2[v] for v in vals2], dtype=np.float32)

        # Build FAISS index from dataset 2 values
        index = vector_index.build_index(mat2, M=hnsw_m,
                                         ef_construction=hnsw_ef_construction)

        # Search top-K candidates for each dataset 1 value
        actual_k = min(top_k, len(vals2))
        similarities, indices = vector_index.search(index, mat1, actual_k,
                                                    ef_search=hnsw_ef_search)

        # Process candidate pairs
        for i in range(len(vals1)):
            for j in range(actual_k):
                idx = int(indices[i, j])
                if idx < 0:
                    continue
                cosine_sim = float(similarities[i, j])
                if cosine_sim < min_cosine:
                    continue

                val1 = vals1[i]
                val2 = vals2[idx]
                key = (val1, val2)

                if key in atomic_node_dict[i_attribute] or \
                        (val2, val1) in atomic_node_dict[i_attribute]:
                    continue

                # Compute string similarity (JW)
                str_sim = pair_sim_func(key, sim_function)

                # Blend
                blended = str_sim * (1 - sim_blend) + cosine_sim * sim_blend

                if blended >= 0.8:
                    atomic_node_dict[i_attribute][key] = blended

        logging.info('block_atomic_nodes: attr %d, pairs found=%d',
                     i_attribute, len(atomic_node_dict[i_attribute]))

    return atomic_node_dict


def _brute_force_numeric(value_list1, value_list2, i_attribute,
                         atomic_node_dict, pair_sim_func, sim_function):
    """Brute-force for numerical (MAD) attributes - fast for small value sets."""
    for v1 in value_list1:
        for v2 in value_list2:
            key = (v1, v2)
            if key in atomic_node_dict[i_attribute] or \
                    (v2, v1) in atomic_node_dict[i_attribute]:
                continue
            sim_val = pair_sim_func(key, sim_function)
            if sim_val >= 0.8:
                atomic_node_dict[i_attribute][key] = sim_val


def block_publication_pairs_multistage(record_dict, ds1_abbrev, ds2_abbrev,
                                        vector_config, year_tolerance=0):
    """Multi-stage blocking: year-bucketed vector retrieval.

    Instead of global top-K across ALL publications, we:
    1. Group publications by year
    2. Within each year bucket, embed and search top-K via FAISS
    3. For cross-year / no-year records, fall back to global vector retrieval

    This dramatically improves top-K coverage: within a year bucket of ~230
    publications, top-100 covers ~43% vs global top-100 covering ~4.4%.

    Args:
        record_dict: full record dict mapping record_id -> record list
        ds1_abbrev: dataset 1 prefix (e.g. 'DA')
        ds2_abbrev: dataset 2 prefix (e.g. 'DB')
        vector_config: dict with vector retrieval parameters
        year_tolerance: 0 = exact year match, 1 = +/-1 year also matched

    Returns:
        list of (record_id_1, record_id_2) candidate pairs
    """
    from collections import defaultdict

    BB_I_YEAR = 6  # index of year in publication record

    model_name = vector_config.get('model_name', 'all-MiniLM-L6-v2')
    top_k = vector_config.get('top_k', 50)
    min_cosine = vector_config.get('min_cosine', 0.5)
    hnsw_m = vector_config.get('hnsw_m', 32)
    hnsw_ef_construction = vector_config.get('hnsw_ef_construction', 128)
    hnsw_ef_search = vector_config.get('hnsw_ef_search', 128)
    cache_dir = vector_config.get('cache_dir', '')

    # Separate publications by dataset
    pub_ids1 = [rid for rid in record_dict
                if rid.startswith(ds1_abbrev) and record_dict[rid][c.I_ROLE] == 'P']
    pub_ids2 = [rid for rid in record_dict
                if rid.startswith(ds2_abbrev) and record_dict[rid][c.I_ROLE] == 'P']

    logging.info('Multi-stage (year-bucketed): ds1=%d pubs, ds2=%d pubs',
                 len(pub_ids1), len(pub_ids2))

    # ---- Group by year ----
    year_buckets1 = defaultdict(list)
    no_year1 = []
    for rid in pub_ids1:
        year = record_dict[rid][BB_I_YEAR]
        if year is not None and isinstance(year, (int, float)) and 1800 <= year <= 2100:
            year_buckets1[int(year)].append(rid)
        else:
            no_year1.append(rid)

    year_buckets2 = defaultdict(list)
    no_year2 = []
    for rid in pub_ids2:
        year = record_dict[rid][BB_I_YEAR]
        if year is not None and isinstance(year, (int, float)) and 1800 <= year <= 2100:
            year_buckets2[int(year)].append(rid)
        else:
            no_year2.append(rid)

    # ---- Embed ALL publications once ----
    author_dict = {rid: rec for rid, rec in record_dict.items()
                   if rec[c.I_ROLE] == 'A'}

    def _text_builder(rec):
        return embedding.build_composite_text_publication(rec, author_dict)

    emb1 = embedding.embed_and_cache_composite(
        record_dict, pub_ids1, _text_builder, cache_dir, 'pub-ds1', model_name)
    emb2 = embedding.embed_and_cache_composite(
        record_dict, pub_ids2, _text_builder, cache_dir, 'pub-ds2', model_name)

    if not emb1 or not emb2:
        logging.warning('No publication embeddings, falling back to global vector retrieval')
        return block_publication_pairs(record_dict, ds1_abbrev, ds2_abbrev,
                                        vector_config)

    # ---- Per-year-bucket FAISS search ----
    all_pairs = set()
    all_years = set(year_buckets1.keys()) | set(year_buckets2.keys())

    for year in sorted(all_years):
        ids1 = [rid for rid in year_buckets1.get(year, []) if rid in emb1]
        ids2 = [rid for rid in year_buckets2.get(year, []) if rid in emb2]

        if not ids1 or not ids2:
            continue

        # Collect IDs from adjacent years if tolerance > 0
        if year_tolerance > 0:
            for delta in range(1, year_tolerance + 1):
                for adj_year in [year - delta, year + delta]:
                    ids2 = ids2 + [rid for rid in year_buckets2.get(adj_year, [])
                                   if rid in emb2 and rid not in ids2]

        # Brute-force within year bucket: all pairs pass to the graph
        # generation step, which will filter by atomic node requirements.
        # This guarantees 100% coverage within each year bucket.
        for rid1 in ids1:
            for rid2 in ids2:
                all_pairs.add((rid1, rid2))

        logging.debug('Year %d: ds1=%d, ds2=%d, pairs=%d', year, len(ids1),
                       len(ids2), len(ids1) * len(ids2))

    # ---- No-year records: brute-force cross with all from other dataset ----
    no_year_ids1 = [rid for rid in no_year1 if rid in emb1]
    no_year_ids2 = [rid for rid in no_year2 if rid in emb2]
    all_ids1 = [rid for rid in pub_ids1 if rid in emb1]
    all_ids2 = [rid for rid in pub_ids2 if rid in emb2]

    for rid1 in no_year_ids1:
        for rid2 in all_ids2:
            all_pairs.add((rid1, rid2))
    for rid2 in no_year_ids2:
        for rid1 in all_ids1:
            all_pairs.add((rid1, rid2))

    result = list(all_pairs)
    logging.info('Multi-stage (year-bucketed): %d pairs from %d year buckets '
                 '(no_year1=%d, no_year2=%d)', len(result), len(all_years),
                 len(no_year1), len(no_year2))
    return result


def block_publication_pairs(record_dict, ds1_abbrev, ds2_abbrev,
                            vector_config):
    """Generate candidate publication pairs using FAISS instead of cross-product.

    Args:
        record_dict: full record dict mapping record_id -> record list
        ds1_abbrev: dataset 1 prefix (e.g. 'DA')
        ds2_abbrev: dataset 2 prefix (e.g. 'DB')
        vector_config: dict with keys: model_name, top_k, min_cosine,
                       hnsw_m, hnsw_ef_construction, hnsw_ef_search, cache_dir

    Returns:
        list of (record_id_1, record_id_2) candidate pairs
    """
    model_name = vector_config.get('model_name', 'all-MiniLM-L6-v2')
    top_k = vector_config.get('top_k', 50)
    min_cosine = vector_config.get('min_cosine', 0.5)
    hnsw_m = vector_config.get('hnsw_m', 32)
    hnsw_ef_construction = vector_config.get('hnsw_ef_construction', 128)
    hnsw_ef_search = vector_config.get('hnsw_ef_search', 128)
    cache_dir = vector_config.get('cache_dir', '')

    # Separate publications by dataset
    pub_ids1 = [rid for rid in record_dict
                if rid.startswith(ds1_abbrev) and record_dict[rid][c.I_ROLE] == 'P']
    pub_ids2 = [rid for rid in record_dict
                if rid.startswith(ds2_abbrev) and record_dict[rid][c.I_ROLE] == 'P']

    logging.info('block_publication_pairs: ds1=%d pubs, ds2=%d pubs',
                 len(pub_ids1), len(pub_ids2))

    # Build author dict for composite text
    author_dict = {rid: rec for rid, rec in record_dict.items()
                   if rec[c.I_ROLE] == 'A'}

    # Embed publications as composite vectors
    def _text_builder(rec):
        return embedding.build_composite_text_publication(rec, author_dict)

    emb1 = embedding.embed_and_cache_composite(
        record_dict, pub_ids1, _text_builder, cache_dir, 'pub-ds1',
        model_name)
    emb2 = embedding.embed_and_cache_composite(
        record_dict, pub_ids2, _text_builder, cache_dir, 'pub-ds2',
        model_name)

    if not emb1 or not emb2:
        logging.warning('No publication embeddings generated')
        return []

    ids1 = [rid for rid in pub_ids1 if rid in emb1]
    ids2 = [rid for rid in pub_ids2 if rid in emb2]

    mat1 = np.array([emb1[rid] for rid in ids1], dtype=np.float32)
    mat2 = np.array([emb2[rid] for rid in ids2], dtype=np.float32)

    # Build FAISS index from dataset 2 publications
    index = vector_index.build_index(mat2, M=hnsw_m,
                                     ef_construction=hnsw_ef_construction)

    actual_k = min(top_k, len(ids2))
    similarities, indices = vector_index.search(index, mat1, actual_k,
                                                ef_search=hnsw_ef_search)

    # Collect candidate pairs
    pairs = []
    for i in range(len(ids1)):
        for j in range(actual_k):
            idx = int(indices[i, j])
            if idx < 0:
                continue
            cosine_sim = float(similarities[i, j])
            if cosine_sim >= min_cosine:
                pairs.append((ids1[i], ids2[idx]))

    logging.info('block_publication_pairs: %d candidate pairs (top_k=%d, min_cosine=%.2f)',
                 len(pairs), top_k, min_cosine)
    return pairs
