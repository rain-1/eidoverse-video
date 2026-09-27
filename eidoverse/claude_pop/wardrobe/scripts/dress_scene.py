#!/usr/bin/env python3
"""Make a dressed COPY of a previous five-lane Claude dance scene.

python eidoverse/claude_pop/wardrobe/scripts/dress_scene.py \
  work/claude_comedy_v03/scenes/buffering_boyband.json

Compatible with the supplied v0.2 ensemble / v0.3 comedy scene players, which
read assets.character_1 ... character_5. No choreography or timing is changed.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ORDER=['sol','nova','prime','pixel','echo']

def asset_path(p):
    try:return p.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:return p.resolve().as_posix()

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter);p.add_argument('scene',type=Path);p.add_argument('--output',type=Path);p.add_argument('--force',action='store_true');a=p.parse_args()
    if not a.scene.is_file():p.error(f'Scene not found: {a.scene}')
    config=json.loads(a.scene.read_text());assets=config.get('assets',{})
    if not all(f'lane_{i}'in assets for i in range(1,6)):p.error('Expected one of our five-lane ensemble/comedy scenes with lane_1 through lane_5 assets.')
    for i,member in enumerate(ORDER,1):
        vrm=Path('work/claude_pop/vrms')/f'claude_{member}.vrm'
        if not vrm.is_file():p.error(f'Missing {vrm.name}; run build_vrms.py first.')
        assets[f'character_{i}']=asset_path(vrm)
    assets['character_vrm']=asset_path(Path('work/claude_pop/vrms/claude_prime.vrm'));config['assets']=assets
    output=a.output or Path('work/claude_pop/scenes')/(a.scene.stem+'_dressed.json')
    if output.resolve()==a.scene.resolve():p.error('Refusing to overwrite the original scene. Choose a different output path.')
    if output.exists() and not a.force:p.error(f'{output} already exists; use --force only to replace the generated copy.')
    output.parent.mkdir(parents=True,exist_ok=True);renders=Path('work/claude_pop/renders');renders.mkdir(parents=True,exist_ok=True);config['outputVideo']=asset_path(renders/(output.stem+'.mp4'));output.write_text(json.dumps(config,indent=2)+'\n')
    print(asset_path(output))
    print('All original clip assignments, offsets, BPM and duration have been retained.')
if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as e:print(f'Cannot dress scene: {e}',file=sys.stderr);sys.exit(1)
