# Co-op connection guide

Co-op setup uses **a private ZeroTier network**. Each
player installs it once and joins the same private network. After that, start
ZeroTier, open the launcher and connect. You normally do not need to change
your router or create port-forwarding rules.

Your PC firewall may still need permission for ZeroTier, the launcher and DTA.
Keep your firewall enabled. ZeroTier avoids the usual router setup; it does not
bypass your PC's firewall or guarantee that every internet connection will work.

The co-op prototype still requires live gameplay verification; follow
[COOP_PLAYTEST.md](COOP_PLAYTEST.md) once the connection is ready.

## One-time ZeroTier setup

1. **Both players:** install ZeroTier from its [official download page](https://www.zerotier.com/download/).
   Windows users can use the tray app; Linux users can follow the
   [official Linux instructions](https://docs.zerotier.com/linux/).
2. **One player:** create a network in ZeroTier Central. Keep it **Private**.
   Follow the [official setup guide](https://docs.zerotier.com/start/) for the
   current dashboard and installation steps.
3. **Network owner:** send the network ID to your partner in a private message.
4. **Both players:** join that network from the ZeroTier app. On Linux, joining
   is also available through `sudo zerotier-cli join NETWORK_ID`, replacing
   `NETWORK_ID` with the network ID from Central.
5. **Network owner:** authorize both PCs in Central's member list. Check their
   device IDs with your partner before authorizing them. A network ID alone
   does not authorize a device on a private network.
6. Wait until both devices are online and have a **Managed IPv4 address**.
   The host privately sends their Managed IPv4 address to the partner. Use
   this address, not the Physical IP, network ID or
   ZeroTier device ID. Do not paste the `/24` or other subnet suffix.

You do not need to recreate the network or authorize the same PCs every time.
For three or four players, repeat joining and authorization for each player.

## Connect in the launcher

Every player needs a matching DTA installation and launcher source/build.
During developer testing, set `COOP_FEATURE_ENABLED = True` in
`randomizer/coop/feature.py` and restart each launcher. Release builds must keep
this flag off until live verification is complete.

1. Start ZeroTier on every PC and check that your private network is connected.
2. Enable **Co-op mode (experimental)** in each launcher. Choose the same player
   count and different player names. Do not leave everyone named `Commander`.
3. For Shop Mode, each player uses their existing personal profile to buy
   permanent upgrades and select units in **Shop Setup** before connecting.
   The host generates the Grid or starts the Shop run.
4. The host opens **Co-op Connection**, selects **Host**, and clicks **Connect**.
   Host ZeroTier IPv4 appears only when **Join** is selected; hosts do not
   enter an IP address in the launcher.
5. The host's **Pairing code** is always visible as a text label, not an input.
   Click **Copy pairing code** to share it with the partner. Each launcher
   generates its own host code; the guest enters the current host's code.
6. Each partner opens the connection window and selects **Join**. Paste the
   host's **ZeroTier Managed IPv4** into Host ZeroTier IPv4 and the host's code into
   Pairing code. Both fields accept paste while hidden. Click **Connect**.
7. The launcher uses lobby TCP `19420` and game UDP `1234` automatically;
   there are no port controls to configure.
8. Wait until every launcher displays the complete player roster. The host
   selects and launches the mission. Guests receive the host's run; their
   selected permanent units and applicable permanent buffs stay personal.
   **Current Loadout** shows only that player’s active units and buffs. Each player sees
   their own Gems and permanent ownership. Select guest units before joining;
   disconnect to change that selection. Permanent purchases remain locked
   while a Shop run is active.

Solo and co-op use the same personal `shop_profile.json`. Switching modes
does not reset Gems or permanent unlocks. Co-op keeps its own run and Ore;
the host controls run purchases and progression. Permanent selected units,
unit buffs, global combat upgrades and starting-credit upgrades apply only
to their owner. A player selecting Artillery cannot build a partner’s Behemoth
unless their own selection or a shared run purchase unlocks it. Run purchases
remain shared, but never copy permanent ownership or buffs between profiles. Powers remain
disabled in this prototype. Every player must use an updated launcher.

**Connected means the launcher lobby works.** Gameplay uses a separate UDP
connection, so play a mission before considering the setup verified.
After the game closes, click **Disconnect** before changing connection settings
or retrying a failed connection. Closing the connection window does not
disconnect an existing session.

### Connection diagnostics

Click **Show connection log** in the connection window to see connection stages,
host rejections, and runtime checks. **Copy connection log** copies these details
for troubleshooting. They are also saved in `RandomizerLauncherData/logs/launcher.log`
for packaged launches, or `RandomizerLauncher/logs/launcher.log` for source launches.
Host launch validation and preparation failures also appear in the connection
log. Guest state synchronization is logged after its views update. Joining
refreshes the host's Grid, mission details, unlock icons, and progress; the
guest's launch buttons become **Suggest Mission**. Disconnecting restores the
guest's previous data and selection.

**Host DTA runtime differs** means the TCP connection reached the host, but the
game files do not match. With updated launchers on both PCs, the error lists the
differing files, and both connection logs include their local and remote SHA-256
hashes. Use the same DTA release and game files on both PCs, then disconnect and
retry. Updating only the launcher does not fix different game files. Runtime
validation remains required to avoid incompatible multiplayer games.

Text compatibility hashes normalize Windows CRLF and Linux LF line endings in
the version file and checked INIs. Identical rules with different line endings
can connect; gameplay value changes and executable/DLL differences still fail.
The log records normalized hashes under `files` and original byte hashes under
`raw_files`. Installed files are never rewritten by this comparison. Both players
need a launcher with the same `fingerprint_policy`; older builds report that the
compatibility check differs and must be updated.

Personal saves, mission completions, Gems, and files inside the randomizer's
data/configuration folders are not part of the installation fingerprint and do
not need to match between players.

Native map and option dependencies use the same newline normalization and
case-independent relative filenames. Windows and Linux catalogue hashes match
for identical content. Existing saved Grid/Shop metadata is upgraded only when
its legacy hashes match the installed content, without resetting progress or
Gems. Actual native map changes still fail validation. An incompatible incoming
snapshot is rejected before replacing guest state, then disconnects once rather
than repeatedly reporting the same error.

Host and Join remember separate pairing codes while the launcher is open.
Switching back to Host restores that launcher's host code; Join retains the code
you entered for the other host. Send the currently hosting launcher's code to
each guest.

## Streaming and private information

In **Host**, the pairing code is always visible and cannot be edited. In **Join**,
the launcher hides **Host ZeroTier IPv4** and the pairing-code input by default.
The pairing code controls lobby admission. Ports and player count do not need
masking.

ZeroTier authorizes devices on the virtual network. The pairing code separately
verifies the intended launcher host and guests, so it remains required for this
lobby protocol. Send the host's code privately to each guest before connecting.

- **Copy pairing code** copies the displayed host code or the entered guest code.
  Keep the host connection window outside a stream if the code should remain private.
- **Show IP and code (visible on stream)** reveals both fields for guests. The
  fields stay revealed while switching roles, connecting, disconnecting, or
  switching away from the window, so another player has time to enter the code.
  Uncheck the box to hide them. Closing the window or copying the code
  hides guest inputs; reopening Join starts hidden. The host label remains visible.
- Connection status/errors redact IP addresses and the current pairing code.
  This protection applies to the launcher's co-op messages, not other programs.
- Keep ZeroTier Central off stream: its member list can display physical
  internet addresses as well as managed network addresses.
- Only authorize intended players on your private ZeroTier network. If you
  accidentally broadcast a pairing code, disconnect everyone, restart the
  host launcher to generate a new code, and share it privately before reconnecting.
- `spawn.ini`, game/debug logs, private messages and clipboard history can
  still contain addresses. Review and redact files before posting them.

Masking protects the screen display. It does not make players anonymous to
one another or remove connection details from native game files.

## Firewall permission, only if needed

Try connecting and launching a mission first. You may only need to accept an
application firewall permission prompt. Do not disable the firewall or put
your PC into a router DMZ.

If blocked, allow these incoming connections **over your private ZeroTier
network**, using the defaults above:

| PC | Required launcher/game traffic |
| --- | --- |
| Host | TCP `19420` for the lobby; UDP `1234` for gameplay |
| Every guest | UDP `1234` for gameplay |

ZeroTier's own service also needs firewall permission. Its documentation
describes UDP `9993` and the virtual network's local firewall behavior:
[ZeroTier firewall and router guidance](https://docs.zerotier.com/routertips/).

On **Windows**, check Windows Security > Firewall & network protection > Allow
an app through firewall for ZeroTier, the launcher (or Python for source
launches), and DTA's `game.exe`. Permissions must apply to the network profile
used by the ZeroTier adapter. If using explicit port rules instead, use Windows
Defender Firewall with Advanced Security and restrict their remote addresses
to your ZeroTier peers or managed network subnet.
See [Microsoft's application firewall instructions](https://support.microsoft.com/en-us/windows/security/firewall/risks-of-allowing-apps-through-windows-firewall).

On **Linux**, ZeroTier installation does not configure every possible firewall.
If UFW is active, an interface-scoped rule can allow only the ZeroTier adapter.
Find its name with `sudo zerotier-cli listnetworks`, then replace
`ZEROTIER_INTERFACE` below with that interface name:

```sh
# Host only: launcher lobby
sudo ufw allow in on ZEROTIER_INTERFACE to any port 19420 proto tcp

# Every player's PC: native game traffic
sudo ufw allow in on ZEROTIER_INTERFACE to any port 1234 proto udp
```

These are optional troubleshooting commands for an existing UFW setup. Do not
enable UFW or change another firewall just to follow this guide. If ZeroTier
itself is blocked, use its official instructions for your firewall first.
The interface-specific rule syntax is documented in the
[Ubuntu UFW manual](https://manpages.ubuntu.com/manpages/resolute/man8/ufw.8.html).

If **firewalld** is running, inspect the ZeroTier interface's zone with
`firewall-cmd --get-zone-of-interface=ZEROTIER_INTERFACE`. If it reports
`no zone`, the default zone applies; find it with
`firewall-cmd --get-default-zone`. Authorization in ZeroTier Central does
not open the launcher port in the host firewall.

Replace `ZONE`, `PEER_ZEROTIER_IP` and `YOUR_ZEROTIER_IP` below with that zone
and the players' Managed IPv4 addresses. These rules permit only that peer's
traffic to your ZeroTier address. Add the TCP rule on the host; add the UDP
rule on every player, once per peer for a three/four-player game.

```sh
sudo firewall-cmd --zone=ZONE --add-rich-rule='rule family="ipv4" source address="PEER_ZEROTIER_IP/32" destination address="YOUR_ZEROTIER_IP/32" port port="19420" protocol="tcp" accept'
sudo firewall-cmd --zone=ZONE --add-rich-rule='rule family="ipv4" source address="PEER_ZEROTIER_IP/32" destination address="YOUR_ZEROTIER_IP/32" port port="1234" protocol="udp" accept'
```

These are runtime rules: they last until firewalld reloads or the PC reboots.
After verifying the connection, repeat each successful command with
`--permanent` to save that specific rule. Do not move the interface into a
trusted zone or save unrelated runtime rules. See the
[firewall-cmd manual](https://firewalld.org/documentation/man-pages/firewall-cmd.html)
and [rich-rule syntax](https://firewalld.org/documentation/man-pages/firewalld.richlanguage.html).

## Troubleshooting

- **`getaddrinfo failed` / invalid IPv4:** replace Host ZeroTier IPv4 with
  the current host's Managed IPv4 only: four numbers separated by dots.
  Do not paste a network ID, pairing code, `/24` suffix, port, or URL.
  The launcher validates this field before attempting the connection.
- **Guest cannot connect:** confirm the host clicked Connect first; both PCs
  joined the same network and were authorized; the guest used the host's
  Managed IPv4 and pairing code; TCP `19420` is allowed on the host.
- **Timeout:** the launcher now distinguishes connecting to the host from
  waiting for its greeting/authentication. If a Windows guest times out while
  connecting, run `Test-NetConnection HOST_ZEROTIER_IP -Port 19420` in
  PowerShell while the host is waiting. `TcpTestSucceeded: False` means the
  TCP lobby cannot be reached; check the host listener, host firewall and
  ZeroTier route before changing the pairing code. See
  [Microsoft's Test-NetConnection reference](https://learn.microsoft.com/en-us/powershell/module/nettcpip/test-netconnection).
- **Pairing/runtime/player-count error:** use the same host code, player count
  and game files on every PC. Names must be distinct.
- **Lobby works, game does not:** check incoming UDP `1234` on every PC, and
  DTA's firewall permission on the ZeroTier adapter. Save the evidence listed
  in COOP_PLAYTEST.md if the native game still fails.
- **Slow or unstable game:** ZeroTier may relay traffic on restrictive networks.
  A successful lobby does not guarantee low latency. Check its
  [network troubleshooting guidance](https://docs.zerotier.com/routertips/).
