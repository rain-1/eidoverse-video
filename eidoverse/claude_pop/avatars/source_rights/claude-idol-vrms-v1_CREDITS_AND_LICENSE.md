# Source credits and unresolved licence metadata

## Attribution

- **Claude suit base model:** digi — https://x.com/digi_dot_exe
- **Claudesona logo-bloom character design:** voooooogel — https://x.com/voooooogel
- **Source repository/distribution:** https://github.com/SkyeShark/eidoverse-video
- **Repository credits inspected:** https://github.com/SkyeShark/eidoverse-video/blob/main/CREDITS.md
- **Wardrobe changes:** new accessory geometry, material/texture treatment, garment reshaping and packaging generated for River in this conversation, 2026-09-09.
- **Motion samples:** the user's previously supplied Claude Comedy v0.3 pack; no new choreography is claimed for the included air_guitar, noodle_arms and rocket_star clips.

## Important discrepancy — not silently resolved

The repository's CREDITS.md calls `claude_suit.vrm` **CC-BY**, without identifying a licence version in that entry. However, the actual supplied VRM 1.0 file embeds the following restrictions:

```json
{
  "avatarPermission": "onlyAuthor",
  "commercialUsage": "personalNonProfit",
  "creditNotation": "required",
  "allowRedistribution": false,
  "modification": "prohibited",
  "licenseUrl": "https://vrm.dev/licenses/1.0/"
}
```

The original also has content-use restriction fields. Its complete original metadata is copied in `source/original_vrm_meta.json` for inspection.

This pack does **not** determine which of the conflicting notices governs, assert that the original metadata is a mistake, or grant permission to redistribute, commercially exploit or modify the underlying character. The edited files preserve the source licence/restriction fields. Only the avatar display name, version and a wardrobe-credit author entry are changed.

Please obtain clarification from the source model owner for the intended use, especially public asset redistribution or commercial video work. Keep the above creator credits with the assets and use the owner's clarified terms. These are requested edited working copies, not a relicensing of the base model.

## Other content

No outside garment models, commercial texture packs, branded idol costumes, stock clothing or font binaries are included. New wardrobe meshes/patterns are procedural designs. The Python tools use separately installed open-source dependencies, which are not bundled. Nothing here changes their licences or the eidoverse engine's licence.
