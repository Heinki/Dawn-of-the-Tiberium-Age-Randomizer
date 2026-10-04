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
3. The host generates the Grid or starts the Shop run.
4. The host opens **Co-op Connection**, selects **Host**, and clicks **Connect**.
   The Host ZeroTier IPv4 field is used only by guests; the host can leave it empty.
5. The host clicks **Copy code privately** and sends the copied code to the
   partner through a private message. This copies the real code while keeping
   it hidden on screen. Each launcher initially generates a different code;
   guests must replace theirs with the host's code.
6. Each partner opens the connection window and selects **Join**. Paste the
   host's **ZeroTier Managed IPv4** into Host ZeroTier IPv4 and the host's code into
   Pairing code. Both fields accept paste while hidden. Click **Connect**.
7. The launcher uses lobby TCP `19420` and game UDP `1234` automatically;
   there are no port controls to configure.
8. Wait until every launcher displays the complete player roster. The host
   selects and launches the mission. Guests receive the host's run and loadout.

**Connected means the launcher lobby works.** Gameplay uses a separate UDP
connection, so play a mission before considering the setup verified.
After the game closes, click **Disconnect** before changing connection settings
or retrying a failed connection. Closing the connection window does not
disconnect an existing session.

## Streaming and private information

The launcher hides **Host ZeroTier IPv4** and **Pairing code** by default. These should
stay hidden on a stream. The pairing code controls lobby admission; viewers
do not need it. Ports and player count do not need masking.

ZeroTier authorizes devices on the virtual network. The pairing code separately
verifies the intended launcher host and guests, so it remains required for this
lobby protocol. Send the host's code privately to each guest before connecting.

- **Copy code privately** does not reveal the code in the launcher. Send it in
  a private message, with your chat window and clipboard history off stream.
- **Show IP and code (visible on stream)** deliberately reveals both. The
  launcher masks them again after 30 seconds, when the connection window loses
  focus, when connecting/disconnecting, and when closing/reopening the window.
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

## Troubleshooting

- **Guest cannot connect:** confirm the host clicked Connect first; both PCs
  joined the same network and were authorized; the guest used the host's
  Managed IPv4 and pairing code; TCP `19420` is allowed on the host.
- **Pairing/runtime/player-count error:** use the same host code, player count
  and game files on every PC. Names must be distinct.
- **Lobby works, game does not:** check incoming UDP `1234` on every PC, and
  DTA's firewall permission on the ZeroTier adapter. Save the evidence listed
  in COOP_PLAYTEST.md if the native game still fails.
- **Slow or unstable game:** ZeroTier may relay traffic on restrictive networks.
  A successful lobby does not guarantee low latency. Check its
  [network troubleshooting guidance](https://docs.zerotier.com/routertips/).
