# Claude Pop for Eidoverse Video

This directory turns the supplied Claude dance and wardrobe packs into reusable
scene assets. It contains 20 distinct avatar variants, five skinned outerwear
builds, 37 fitted accessory meshes, a separate 25-piece accessory style kit,
and 601 distinct VRMA files.
`motions/catalog.json` maps every source clip to its committed path and SHA-256.
The source ZIPs include duplicate files; the catalog retains all source paths
without committing duplicate VRMA bytes.

## Make the five dressed avatars

From the repository root:

```bash
python -m pip install numpy
python eidoverse/claude_pop/wardrobe/scripts/build_vrms.py
mkdir -p work/claude_pop/renders
python eido.py render eidoverse/claude_pop/wardrobe/scenes/lineup.json --probe
python eido.py render eidoverse/claude_pop/pop_dance.json
```

The builder reads the existing `eidoverse/assets/vrms/claude_suit.vrm` and
writes Prime, Pixel, Nova, Echo, and Sol to `work/claude_pop/vrms/`. It keeps
the source avatar untouched, preserves its humanoid and creator credits, and
sets the generated VRMs' embedded terms to CC BY 4.0.
It accepts `--only prime`, `--inspect`, `--attachments-only`, `--fit-config`,
and `--source` for other local avatars. The included scene JSONs show the
five-person lineup and individual closeups. `pop_dance.json` renders Prime
with a suit-calibrated clip through the existing VRMA player. Change its
`character_vrm` and `dance` asset paths to cast a different member or clip.

The output VRMs are generated into ignored `work/`, as are video renders.
Check the generated `fitting_report.json` and a motion probe before using
the wardrobe in a finished shot. These meshes are fitted to the rest rig;
there is no cloth or accessory collision simulation.

## Cast a supplied avatar

`avatars/catalog.json` gives the committed path, family, SHA-256 and source ZIP
for each of the 20 distinct VRMs. They are grouped into Context Crew,
Afterglow, Petalpop and Idol variants. Set `config.assets.character_vrm` to
one of those paths and load it through the existing `VRMLoaderPlugin`. The
`pop_dance.json` example can be pointed at one of these files directly, so
the builder is optional when using a supplied look.

## Motion and accessories

`motions/` contains the distinct animation bytes from Volume 1, both Volume
2 branches, Dance v0.1, Ensemble v0.2, and Comedy v0.3. The source `classic`
and `suit` variants are separate rig calibrations. Use a suit clip with a
derived suit avatar. The `manifest.json`, group, and routine JSON files are
kept beside each collection. They describe arrangements; a group performance
needs its per-actor clips and timing applied to separate avatars. The sample
scene demonstrates the single-actor route supported by the renderer.

`wardrobe/assets/`, `wardrobe/garments/`, and `wardrobe/textures/` contain
the geometry and maps consumed by the local builder. The earlier independent
accessory designs are in `accessory_styles/`, with their look and asset
manifests. Those meshes can be used as GLB props or fitted with the styling
helper from the source pack; their placements have not been verified on the
current Claude rig.

## Source and publication boundary

The avatar variants and new pack assets are contributed by the creator under
the [Claude Pop asset terms](ASSET_LICENSE.md). The underlying Claude suit
and character design remain credited in `CREDITS.md`. The contributed VRMs'
embedded permissions are set to match the CC BY 4.0 grant.

The source material came from the INGRESS packs listed in
[`SOURCE_INVENTORY.md`](SOURCE_INVENTORY.md). Offline viewers, embedded model
copies, preview videos, validation outputs, and duplicate ZIP copies are not
runtime assets and are omitted. Keep the credits in
`wardrobe/CREDITS_AND_TERMS.txt` and `accessory_styles/CREDITS_AND_RIGHTS.md`
with any redistribution. The source Claude suit is credited to digi and the
claudesona design to voooooogel in the repository's `CREDITS.md`.
