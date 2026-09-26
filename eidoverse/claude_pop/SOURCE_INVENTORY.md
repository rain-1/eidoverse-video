# INGRESS source inventory

All 18 ZIPs were unpacked and inspected. SHA-256 here identifies each supplied archive. Duplicate `(1)` ZIPs contain the same bytes as their namesake. The Windows `:Zone.Identifier` sidecars are download metadata.

| Archive | Size (MiB) | SHA-256 | Integration |
| --- | ---: | --- | --- |
| `Claude_Dance_Pack_v1(1).zip` | 12.2 | `cb35701887c11a4edf7ecc2c140c9ecfd805fb25b719735b4eed8ce227a65859` | Duplicate archive; omitted |
| `Claude_Dance_Pack_v1.zip` | 12.2 | `cb35701887c11a4edf7ecc2c140c9ecfd805fb25b719735b4eed8ce227a65859` | Distinct VRMA and arrangement data integrated |
| `Claude_Dance_Pack_v2(1).zip` | 23.8 | `999af82d84fa904acd063517b60763c82a68d85fdac51e8ab03927622f25affc` | Duplicate archive; omitted |
| `Claude_Dance_Pack_v2.zip` | 23.8 | `999af82d84fa904acd063517b60763c82a68d85fdac51e8ab03927622f25affc` | Distinct VRMA and arrangement data integrated |
| `Claude_Dance_Pack_v2_Chaos_Encore(1).zip` | 23.6 | `8e731cbdc42c5c0d7b019ab8366ead60a70aa31ab831bd894b4b05aea64d7737` | Duplicate archive; omitted |
| `Claude_Dance_Pack_v2_Chaos_Encore.zip` | 23.6 | `8e731cbdc42c5c0d7b019ab8366ead60a70aa31ab831bd894b4b05aea64d7737` | Distinct VRMA and arrangement data integrated |
| `Claude_Five_VRMs.zip` | 14.3 | `953c97217c055025153940dcec81f4935b49a3e6e1ce03060a00a85d8664ab02` | Distinct avatars, provenance in `avatars/` |
| `Claude_KPop_5_VRMs.zip` | 24.2 | `6ab26a6c79c07c89a483eaf002e263aef7084c44df905feed96a7da36ca7456f` | Distinct avatars, provenance in `avatars/` |
| `Claude_KPop_Wardrobe_Studio(1).zip` | 36.8 | `f377861a8b12132b03364912fd029623b0cfd52f9f970cc8cc341463f46b71bb` | Duplicate archive; omitted |
| `Claude_KPop_Wardrobe_Studio.zip` | 36.8 | `f377861a8b12132b03364912fd029623b0cfd52f9f970cc8cc341463f46b71bb` | Avatar duplicates; source docs checked |
| `Claude_Kpop_Five_Complete.zip` | 42.7 | `c45b29ceb2350b10e855862357cbc3abde17b45200d7b4412919a015a4d400b7` | Avatar duplicates; source docs checked |
| `PETALPOP_5_Edited_Claude_VRMs.zip` | 27.2 | `7aa7ba457aa6b7ec9343d2dd229440354edbf6a4f3010c0976e69f86a62606dc` | Distinct avatars, provenance in `avatars/` |
| `claude-comedy-pack-v0.3.zip` | 16.7 | `94022549bdcbed77441c2b55cb38850859394c7058bf4cc2d22337b81556e257` | Distinct VRMA and arrangement data integrated |
| `claude-dance-pack-v0.1.zip` | 2.2 | `476fe0d7c2b2e25e85d63c26d9b11081358850e45ec746d4989a2ec4f008b406` | Distinct VRMA and arrangement data integrated |
| `claude-ensemble-pack-v0.2.zip` | 19.2 | `ba25aecfb39e619e25c152aeb6c5abccc3d8d5430f767893d5f908c55b8dfe20` | Distinct VRMA and arrangement data integrated |
| `claude-idol-vrms-v1.zip` | 39.5 | `8f5079749571f8794ee70dc34d9f1dd18daf4e7982bdba86d92796bdb29bfcf8` | Distinct avatars, provenance in `avatars/` |
| `claude-idol-wardrobe-pack-v1.zip` | 12.2 | `fc0c9cef0ef668cbba2a56d461efb7f04924b3a8f10be727835b81021a36cec6` | Meshes, textures, manifests and builder integrated |
| `claude-idol-wardrobe-v1.zip` | 6.0 | `6339b9be763f1728323467088e3bcc5643bb8ff2761e94b2a429a5f1abbd8526` | Meshes, textures, manifests and builder integrated |

Self-contained HTML audition viewers, embedded avatar copies, preview media, generated test reports, and development-only build outputs were inspected but omitted from the public runtime set. `motions/catalog.json` records all VRMA source paths, including duplicates that map to one committed clip. `avatars/catalog.json` records every committed avatar.
