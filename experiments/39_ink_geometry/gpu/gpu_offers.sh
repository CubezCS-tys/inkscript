#!/bin/bash
# Offers passing the owner's rules, cheapest first:  gpu_offers.sh [RTX_5090|RTX_A6000|L40S|...]
# datacenter, verified, reliability >= 0.99, 16+ cores, inet up/down >= 300 Mbps, CUDA >= 12.9 (cu129 wheels), disk >= 150 GB.
G=${1:-RTX_5090}
~/.local/venvs/vast/bin/vastai search offers "gpu_name=$G num_gpus=1 datacenter=True verified=True reliability>=0.99 cpu_cores_effective>=16 inet_down>=300 inet_up>=300 cuda_vers>=12.8 disk_space>=60 rentable=True" -o 'dph+' --raw \
 | python3 -c "
import json,sys
for o in json.load(sys.stdin)[:8]: print(o['id'], round(o['dph_total'],3), o['geolocation'], round(o['inet_down']), round(o['inet_up']), 'cuda', o.get('cuda_max_good'), 'disk_bw', round(o.get('disk_bw',0)), 'ram', o.get('gpu_ram'), 'rel', round(o.get('reliability2', o.get('reliability',0)),3))
"
