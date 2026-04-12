# RELATER - Vector Embedding Module
#
# Encapsulates sentence-transformers model loading and text embedding.
# Lazy-loaded: only initialized when vector blocking is enabled.

import hashlib
import logging
import os
import pickle

import numpy as np

from common import constants as c

_model = None
_model_name = None


def get_model(model_name='all-MiniLM-L6-v2'):
    """Return cached sentence-transformer model, initializing if needed."""
    global _model, _model_name
    if _model is None or _model_name != model_name:
        from sentence_transformers import SentenceTransformer
        logging.info('Loading embedding model: %s', model_name)
        _model = SentenceTransformer(model_name)
        _model_name = model_name
    return _model


def embed_texts(texts, model_name='all-MiniLM-L6-v2', batch_size=256):
    """Embed a list of strings. Returns (N, dim) float32 L2-normalized array."""
    model = get_model(model_name)
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False,
                             normalize_embeddings=True)
    return np.ascontiguousarray(embeddings, dtype=np.float32)


def _cache_path(base_dir, model_name, suffix):
    """Generate a cache file path that includes a model name hash."""
    h = hashlib.md5(model_name.encode()).hexdigest()[:8]
    return os.path.join(base_dir, 'emb-{}-{}.pickle'.format(suffix, h))


def embed_and_cache_values(record_list, attr_index, cache_dir,
                           model_name='all-MiniLM-L6-v2'):
    """Extract unique values at attr_index, embed them, cache to disk.

    Returns dict {value_string: numpy_vector}.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = _cache_path(cache_dir, model_name, 'val-{}'.format(attr_index))

    if os.path.exists(cache_file):
        logging.info('Loading cached embeddings from %s', cache_file)
        with open(cache_file, 'rb') as f:
            return pickle.load(f)

    # Extract unique non-None string values
    unique_vals = sorted({r[attr_index] for r in record_list
                          if r[attr_index] is not None and r[attr_index] != ''})
    if not unique_vals:
        result = {}
    else:
        logging.info('Embedding %d unique values for attr %d', len(unique_vals), attr_index)
        vectors = embed_texts(unique_vals, model_name)
        result = {v: vectors[i] for i, v in enumerate(unique_vals)}

    with open(cache_file, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    logging.info('Cached embeddings to %s', cache_file)
    return result


def embed_and_cache_composite(record_dict, record_ids, text_builder,
                              cache_dir, suffix,
                              model_name='all-MiniLM-L6-v2'):
    """Embed composite representations for a set of records.

    Args:
        record_dict: full record dict (id -> record list)
        record_ids: list of record IDs to embed
        text_builder: callable(record) -> str
        cache_dir: directory for cache files
        suffix: cache file name suffix
        model_name: sentence-transformer model name

    Returns:
        dict {record_id: numpy_vector}
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = _cache_path(cache_dir, model_name, suffix)

    if os.path.exists(cache_file):
        logging.info('Loading cached composite embeddings from %s', cache_file)
        with open(cache_file, 'rb') as f:
            return pickle.load(f)

    texts = []
    ids = []
    for rid in record_ids:
        rec = record_dict[rid]
        text = text_builder(rec)
        if text:
            texts.append(text)
            ids.append(rid)

    if not texts:
        result = {}
    else:
        logging.info('Embedding %d composite records (%s)', len(texts), suffix)
        vectors = embed_texts(texts, model_name)
        result = {rid: vectors[i] for i, rid in enumerate(ids)}

    with open(cache_file, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    logging.info('Cached composite embeddings to %s', cache_file)
    return result


def build_composite_text_publication(record, author_dict=None):
    """Build composite text from a publication record.

    Format: "title: X venue: Y year: Z authors: A, B"
    """
    parts = []
    title = record[c.BB_I_PUBNAME]
    if title:
        parts.append('title: {}'.format(title))
    venue = record[c.BB_I_VENUE]
    if venue:
        parts.append('venue: {}'.format(venue))
    year = record[c.BB_I_YEAR]
    if year is not None:
        parts.append('year: {}'.format(year))
    # Append author names if available
    if author_dict is not None:
        author_ids = record[c.BB_I_AUTHOR_ID_LIST]
        if author_ids:
            names = []
            for aid in author_ids:
                arec = author_dict.get(aid)
                if arec is not None:
                    name = arec[c.BB_I_FULLNAME]
                    if name:
                        names.append(name)
            if names:
                parts.append('authors: {}'.format(', '.join(names)))
    return ' '.join(parts) if parts else None


def build_composite_text_author(record):
    """Build composite text from an author record.

    Format: "fname: X sname: Y pubname: Z"
    """
    parts = []
    fname = record[c.BB_I_FNAME]
    if fname:
        parts.append('fname: {}'.format(fname))
    sname = record[c.BB_I_SNAME]
    if sname:
        parts.append('sname: {}'.format(sname))
    pubname = record[c.BB_I_PUBNAME]
    if pubname:
        parts.append('pubname: {}'.format(pubname))
    return ' '.join(parts) if parts else None
