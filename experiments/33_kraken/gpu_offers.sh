#!/bin/bash
# The offers passing the owner's rules, cheapest first:  gpu_offers.sh [RTX_5090|RTX_4090]
G=${1:-RTX_5090}
~/.local/venvs/vast/bin/vastai search offers "gpu_name=$G num_gpus=1 datacenter=True verified=True reliability>=0.995 cpu_cores_effective>=16 disk_bw>=2000 inet_down>=300 inet_up>=300 rentable=True" -o 'dph+' --raw \
 | python3 -c "
import json,sys
for o in json.load(sys.stdin)[:12]: print(o['id'], round(o['dph_total'],3), o['geolocation'], o.get('public_ipaddr'), round(o['inet_down']), round(o['inet_up']))
"
