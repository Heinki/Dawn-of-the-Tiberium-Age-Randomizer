# Playing Dawn of the Tiberium Age with Archipelago

This guide explains how to install the DTA Randomizer APWorld, create a player
YAML, connect to a room, and continue an existing multiworld game.

## What you need

- Dawn of the Tiberium Age 15.1.0 with Vinifera in a separate, unmodified game
  installation
- DTA Randomizer Launcher 1.0
- Archipelago 0.6.7
- `dta.apworld` from the same Randomizer release as the launcher

Use matching launcher and APWorld releases. A YAML created by another
Randomizer version or catalogue may be rejected during generation or
connection.

## Install the Randomizer

1. Put `DTARandomizer.exe` in the DTA game root.
2. Confirm that it is beside `DTA.exe`, `game.exe`, `LaunchVinifera.dat`, and
   `Vinifera.dll`.
3. Start `DTARandomizer.exe`.

Use a separate DTA installation for the Randomizer. Do not install it over a
game folder containing unrelated rule or map modifications.

## Install the APWorld

1. Close all Archipelago programs.
2. Copy `dta.apworld` into Archipelago's `custom_worlds` folder.
3. Restart the Archipelago Launcher.

Every person who generates or hosts the room needs this APWorld installed.
Other players do not need DTA unless they are playing the DTA slot.

## Create your player YAML

The launcher exports the YAML needed by Archipelago from the exact values
visible in the Randomizer.

1. Open the Randomizer launcher.
2. Choose the campaigns, progression mode, Grid options, rewards, difficulty,
   and other settings you want.
3. Open the **Archipelago** tab.
4. Enter the exact slot name that you will use in the room.
5. Select **Save Player YAML** and choose where to save the file.
6. Give the YAML to the room host, or place it in Archipelago's `Players`
   folder if you are generating the room yourself.

**Save Player YAML** generates the deterministic AP run and exports a fresh
player file in one operation. A separate standalone seed is not required, and
there is no YAML import step in the launcher. To change the run, change the
visible launcher settings and save a new YAML before generating a new room.

The YAML contains readable `launcher_settings` plus a checksum-protected
`run_manifest` holding the mission order, Grid, reward locations, placements,
and compatibility data for that exact run. Do not edit the generated manifest
by hand. Archipelago rejects readable settings that no longer match it.

## Generate and host the room

1. Install `dta.apworld` for the person generating the room.
2. Put every participant's YAML in Archipelago's `Players` folder.
3. Generate the multiworld normally with Archipelago 0.6.7.
4. Host or upload the generated output using the normal Archipelago workflow.

Do not replace the DTA YAML after the room has been generated. A newly exported
YAML describes a different run and will not match the existing room.

## Connect the launcher

1. Open the room page and find its game-server port.
2. Open the Randomizer's **Archipelago** tab.
3. For a hosted room, leave **Server** as `archipelago.gg`.
4. Enter the game-server port from the room page.
5. Enter the exact slot name used in the YAML.
6. Enter the room password when one is required.
7. Select **Connect**.

Do not paste the browser room URL into the server field. Hosted rooms use the
bare `archipelago.gg` host plus the separate game-server port. The launcher
automatically uses secure WebSocket (`wss://`) for hosted rooms. Custom and
local servers may use their own hostname and port.

When validation succeeds, the connection status turns green and reads
**Connected — AP rewards active**. The launcher then loads the seed, mission
list, Grid, unlocks, completed checks, and progression from the Archipelago
server. Gameplay settings controlled by the room become read-only while
connected.

## Play and report checks

Launch missions through the Randomizer as usual. DTA exposes mission victory
as the reliable progression check, so the launcher reports mission completion
to the server automatically after the Vinifera score-screen victory event.
Items sent to your slot enter the normal Randomizer unlock pipeline and apply
when missions are prepared.

The Archipelago activity panel shows server and item messages. Its chat field
accepts normal chat and server commands such as `!hint` and `!release`.

## Disconnect and continue later

Disconnecting restores the latest standalone Randomizer state and settings.
The mission views, Grid, and Unlocks page refresh to show that local state.

Reconnect to the same room and slot to load the current Archipelago state
again. The server remains authoritative for AP checks, received items, mission
completion, and progression. Pending checks are synchronized after reconnecting
without granting their rewards twice.

## Troubleshooting

### The launcher cannot connect

- Use `archipelago.gg`, not the browser room URL.
- Copy the room's game-server port exactly.
- Match the slot name exactly, including spaces and capitalization.
- Enter the room password if the host configured one.
- Confirm that the room is running and has not expired.

### Version, catalogue, or manifest mismatch

- Use `DTARandomizer.exe` and `dta.apworld` from the same release.
- Generate the room with that APWorld installed.
- Use the YAML that generated this room, not a newer replacement YAML.
- If settings must change, save a new YAML and generate a new room.

### The wrong missions or unlocks are visible

- Confirm that connection status is green.
- Confirm that you connected to the intended room and slot.
- Disconnect to view standalone state; reconnect to restore AP state.

### A completed mission has not appeared

- Keep the launcher running while playing the mission.
- Return to the launcher and confirm that it is still connected.
- Reconnect to request synchronization from the server.
- Check the activity panel and `RandomizerLauncherData/logs/launcher.log` for
  a server refusal or compatibility message.

Live multiworld connection and end-to-end item receipt still require broader
verification. Report reproducible failures with the launcher log, mission
code, room setup, and connection status.
