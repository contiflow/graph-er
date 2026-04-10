# -*- coding: utf-8 -*-
"""
RELATER launcher: argparse + optional YAML config, then runs the legacy pipeline.

The upstream implementation reads ``sys.argv`` inside ``common.settings`` and
``common.hyperparams`` at import time. This entry point rebuilds ``sys.argv``
before loading ``er.bib_er`` so you get explicit flags instead of positional-only
arguments.

Requires **Python 2.7** and the same dependencies as the original RELATER code
(NetworkX, Pandas, etc.). Optional ``--config`` needs PyYAML.
"""
from __future__ import print_function

import argparse
import os
import pickle
import runpy
import sys

_INNER = os.path.dirname(os.path.abspath(__file__))


def _merge_config(config_path):
  try:
    import yaml
  except ImportError:
    print('error: install PyYAML to use --config, or pass flags on the CLI',
          file=sys.stderr)
    sys.exit(1)
  with open(config_path, 'r') as f:
    load = getattr(yaml, 'safe_load', None) or yaml.load
    data = load(f)
  if not isinstance(data, dict):
    print('error: config root must be a mapping', file=sys.stderr)
    sys.exit(1)
  return data


def _build_argv(prog, dataset, atomic_t, bootstrap_t, merge_t, wa, bridges_n,
                scenario_prefix):
  argv = [
    prog, dataset, str(atomic_t), str(bootstrap_t), str(merge_t), str(wa),
    str(bridges_n)
  ]
  if scenario_prefix:
    argv.append(str(scenario_prefix))
  return argv


def main():
  parser = argparse.ArgumentParser(
    description='Run RELATER bibliographic ER pipeline (er.bib_er).')
  parser.add_argument(
    '--config', '-c', metavar='FILE',
    help='YAML file with keys: dataset, atomic_t, bootstrap_t, merge_t, '
    'wa, bridges_n, scenario_prefix (optional)')
  parser.add_argument('dataset', nargs='?', help='e.g. dblp-acm1')
  parser.add_argument('--atomic-t', type=float, dest='atomic_t')
  parser.add_argument('--bootstrap-t', type=float, dest='bootstrap_t')
  parser.add_argument('--merge-t', type=float, dest='merge_t')
  parser.add_argument('--wa', type=float, dest='wa')
  parser.add_argument('--bridges-n', type=float, dest='bridges_n')
  parser.add_argument('--scenario-prefix', default='', dest='scenario_prefix')

  args = parser.parse_args()
  cfg = _merge_config(args.config) if args.config else {}

  def pick(name, argval, default):
    if argval is not None:
      return argval
    if name in cfg:
      return cfg[name]
    return default

  dataset = args.dataset or cfg.get('dataset')
  if not dataset:
    parser.error('dataset: pass positional or set in --config')

  atomic_t = pick('atomic_t', args.atomic_t, 0.9)
  bootstrap_t = pick('bootstrap_t', args.bootstrap_t, 0.95)
  merge_t = pick('merge_t', args.merge_t, 0.85)
  wa = pick('wa', args.wa, 0.9)
  bridges_n = pick('bridges_n', args.bridges_n, 10.0)
  scenario_prefix = args.scenario_prefix or cfg.get('scenario_prefix', '')

  new_argv = _build_argv(parser.prog or 'run_relater', dataset, atomic_t,
                         bootstrap_t, merge_t, wa, bridges_n, scenario_prefix)

  if _INNER not in sys.path:
    sys.path.insert(0, _INNER)

  # Compatibility shim for newer NetworkX versions on Python 3.
  try:
    import networkx as nx
    if not hasattr(nx, 'write_gpickle'):
      def _write_gpickle(obj, path):
        with open(path, 'wb') as f:
          pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)

      def _read_gpickle(path):
        with open(path, 'rb') as f:
          return pickle.load(f)

      nx.write_gpickle = _write_gpickle
      nx.read_gpickle = _read_gpickle
  except Exception:
    pass

  sys.argv = new_argv
  runpy.run_module('er.bib_er', run_name='__main__')


if __name__ == '__main__':
  main()
