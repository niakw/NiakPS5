# Release checks / Contrôles avant essai PS5

This checklist records independently observable results. A CI green light confirms only host tests, native packaging and OpenGL previews—not gameplay on hardware.

| Élément / Area | Verified / Vérifié | Still needs console check / À valider |
| --- | --- | --- |
| PLDmgr broker | 48 IDs from two snapshots; local PING active on target PS5 13.60 | Long-session stability and different users |
| Native game library | Visible on target console | Updated game/app classifications including ShadowMount and media titles |
| Play / Jouer | A homebrew game opened from NiakPS5 | Return after closing a game; entitlement/disc-required error is owned by Sony |
| Artwork | 14,951 verified LaunchBox metadata matches in successful CI build; existing private-cache integrity tests | Native HTTPS artwork download and next-launch cache, PS4 back mixed with matching PS5 front, distinct PC screenshots |
| Descriptions | Maximum three sourced sentences / 360 characters in code and tests | Real-screen truncation and available French text |
| Localization | FR control and genre strings reviewed in staging | Full settings/glyph check with actual PS5 display |
| Settings | UI diagnostics positioned in the right rail in code | No overlap at 1080p on-console and experimental PS5 settings shortcut |
| Wallpaper | Source title/date caption supplied by packaged wallpaper metadata | Captions readable on chosen backgrounds |
| Return after game | One-shot broker return gate with 10-second stable Sony Home guard, host-tested | Actual PS5 close-game lifecycle and disc-refusal behavior |
| Security | Six reported CodeQL patterns patched; host validation | CodeQL findings must be confirmed closed by a subsequent scan |
| Distribution | One merge-only `data/` FTP tree; PLDmgr autoload untouched | New title registration varies by firmware |
| Documentation | FR/EN marketing README, real Mesa screenshot, GitHub issue/security templates | Repository About description/topics need a maintainer's UI action |

**No repeated console tests** for source-only changes. First require current-HEAD native build, full six-angle preview, home screenshot and validated FTP ZIP. Then perform one focused hardware session to establish what still fails.

**Privacy:** Never attach private FTP listings, account images, passwords, keys or personally identifiable logs to an issue.
