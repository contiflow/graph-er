# RELATER - constRaints and attributE values, reLationships, Ambiguity, and 
#           refinemenT for Entity Resolution
# An unsupervised graph-based entity resolution framework that is focused on
# resolving the challenges associated with resolving complex entities. We 
# propose a global method to propagate merging decisions by propagating 
# attribute values and constraints to capture dynamically changing attribute
# values and different relationships, a method for leveraging ambiguity in 
# the ER process, an adaptive method of incorporating relationship structure,
# and a dynamic refinement step to improve entity clusters by unmerging 
# likely wrong links. RELATER can be employed to resolve records of both 
# basic and complex entities. 
#
#
# Nishadi Kirielle, Peter Christen, and Thilina Ranbaduge
#
# Contact: nishadi.kirielle@anu.edu.au
#
# School of Computing, The Australian National University, Canberra, ACT, 2600
# -----------------------------------------------------------------------------
#
# Copyright 2021 Australian National University and others.
# All Rights reserved.
#
# -----------------------------------------------------------------------------
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =============================================================================
import sys
from common import constants as c

data_set = sys.argv[1]
atomic_t = float(sys.argv[2])  # 0.9
bootstrap_t = float(sys.argv[3])  # 0.95
merge_t = float(sys.argv[4])  # 0.85

wa = float(sys.argv[5]) # 0.90
bridges_n = float(sys.argv[6]) # 10
scenario_prefix = sys.argv[7] if len(sys.argv) == 8 else ''

# Temporal Constraints

# Link Constraints

# Vector retrieval parameters (optional, keyword-based args after position 7)
use_vector_blocking = False
vector_model = 'all-MiniLM-L6-v2'
vector_top_k = 50
vector_min_cosine = 0.5
vector_sim_blend = 0.0
vector_hnsw_m = 32
vector_hnsw_ef_construction = 128
vector_hnsw_ef_search = 128
vector_block_atomic = False  # If False, only block publication pairs (atomic nodes stay brute-force)
year_tolerance = 0  # Year tolerance for multi-stage blocking (0=exact, 1=+/-1 year)

i = 7
while i < len(sys.argv):
  arg = sys.argv[i]
  if arg == '--use-vector-blocking' and i + 1 < len(sys.argv):
    use_vector_blocking = sys.argv[i + 1].lower() in ('true', '1', 'yes')
    i += 2
  elif arg == '--vector-model' and i + 1 < len(sys.argv):
    vector_model = sys.argv[i + 1]
    i += 2
  elif arg == '--vector-top-k' and i + 1 < len(sys.argv):
    vector_top_k = int(sys.argv[i + 1])
    i += 2
  elif arg == '--vector-min-cosine' and i + 1 < len(sys.argv):
    vector_min_cosine = float(sys.argv[i + 1])
    i += 2
  elif arg == '--vector-sim-blend' and i + 1 < len(sys.argv):
    vector_sim_blend = float(sys.argv[i + 1])
    i += 2
  elif arg == '--vector-hnsw-m' and i + 1 < len(sys.argv):
    vector_hnsw_m = int(sys.argv[i + 1])
    i += 2
  elif arg == '--vector-hnsw-ef-construction' and i + 1 < len(sys.argv):
    vector_hnsw_ef_construction = int(sys.argv[i + 1])
    i += 2
  elif arg == '--vector-hnsw-ef-search' and i + 1 < len(sys.argv):
    vector_hnsw_ef_search = int(sys.argv[i + 1])
    i += 2
  elif arg == '--vector-block-atomic' and i + 1 < len(sys.argv):
    vector_block_atomic = sys.argv[i + 1].lower() in ('true', '1', 'yes')
    i += 2
  elif arg == '--year-tolerance' and i + 1 < len(sys.argv):
    year_tolerance = int(sys.argv[i + 1])
    i += 2
  else:
    i += 1

scenario = '{}relater-ta{}-tm{}-wa{}-tn{}'.format(scenario_prefix, atomic_t, merge_t, wa, bridges_n)
if use_vector_blocking:
  scenario += '-vec-k{}-cos{}-blend{}-m{}-efc{}-efs{}'.format(
    vector_top_k, vector_min_cosine, vector_sim_blend,
    vector_hnsw_m, vector_hnsw_ef_construction, vector_hnsw_ef_search)
  if year_tolerance > 0:
    scenario += '-yt{}'.format(year_tolerance)
c.__init_constants__(data_set)
