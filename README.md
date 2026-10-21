# MeshCore bot starter kit

Everything you need to run your own **MeshCore bot** on a Raspberry Pi, with a **KISS modem radio** or a
regular **companion radio** (USB, Wi-Fi or Bluetooth): a few setup questions and your bot is on the mesh. Add
your own commands without touching any code.

It works with **three kinds of radio setup**, see [Choose your setup](#choose-your-setup). The radio and node setup
comes from **VLK-Bot** on the Central Valley (California) mesh. The bot here is a separate, simpler starter bot:
VLK-Bot itself is private for now.

## What the bot does

A simple, friendly bot you can build on:

| Command | Reply |
|---|---|
| `test` | `@[Sam] ack: 3 hops \| 4f4c→3a50→1145`: how many hops your message took, and through which repeaters |
| `ping` | `pong` |
| `help` | The command list, including yours |
| **your own** | Anything you add during setup, e.g. `rules` → "Be kind, no spam." |

People use commands by **DM**, or in a channel with **`@[YourBot] command`**. In your test channel a plain
**`test`** works on its own. The bot never talks in channels you mark as quiet (like Public), and answers each
person at most once every 30 seconds (you can change this).

Optional add-on: [alerts for your area](#optional-alerts-for-your-area) (earthquakes, weather, wildfires, air quality,
rivers, space weather) posted to a channel.

## Choose your setup

The bot runs inside **RemoteTerm** (a web UI for MeshCore that can run bot code). What differs is how RemoteTerm
reaches your radio:

| | **A. KISS modem radio** | **B. Companion radio over USB** |
|---|---|---|
| Radio firmware | MeshCore **KISS modem** | MeshCore **companion** (the normal firmware phones connect to) |
| Where the node runs | on the Pi (meshcore-pi): keys and routing on the Pi | on the radio itself |
| Connection | USB → meshcore-pi → RemoteTerm | USB → RemoteTerm directly |
| Install | `./install.sh` does everything | install RemoteTerm, then the bot (steps below) |
| Good for | several identities on one radio, keys kept off the radio | the simplest setup, if you already have a companion radio |

**C. Station G3 with a Pi Zero 2 W:** the Pi plugs into the G3 and drives its 1 W radio **through its pins**
(SPI), with no USB radio at all. It works like A (meshcore-pi on the Pi), and `./install.sh` handles it. See Setup C.

Not sure? If your radio already works with the MeshCore phone app, it's running **companion** firmware: use **B**.
A companion radio over **Wi-Fi or Bluetooth** works the same way as B. Choose TCP or BLE instead of Serial
in RemoteTerm's installer.

### Which setup for my radio?

| Radio | Setup A (KISS) | Setup B (companion over USB) | Notes |
|---|---|---|---|
| **RAK4631 / WisBlock** (RAK19007, RAK19003…) | ✅ tested (`RAK_4631_kiss_modem`) | ✅ | The radio this kit was built on. |
| **Station G3** with its own MeshCore board | ? only if a KISS build exists for it | ✅ | 1 W radio. Flash MeshCore **companion** firmware and use B. |
| **Station G3** with a **Pi Zero 2 W** as its computer | – | – | Use **Setup C**: the Pi drives the G3's radio through its pins. |
| **Heltec V3/V4, LilyGO T-Beam / T3-S3, Seeed XIAO**, other boards | ? check for a `*_kiss_modem` build | ✅ | Any board with MeshCore companion firmware works with B. |

**? = check MeshCore's releases** for a file named `<your board>_kiss_modem`. If there isn't one, use Setup B.
**When in doubt, use Setup B:** companion firmware exists for nearly every MeshCore board.
High-power boards (1 W, like the G3) need a good antenna and a solid power supply; lower the transmit power if
the antenna is close to other radios.

**What you need (both):** a **Raspberry Pi** (3, 4, 5 or Zero 2 W) with Raspberry Pi OS (Bookworm or newer)
and internet; a **LoRa radio MeshCore supports** (e.g. RAK4631) **with an antenna**; a USB cable to the Pi.
**Never power a radio without its antenna.**

## Setup A: KISS modem radio (about 15 minutes)

**1. Flash the radio with the KISS modem firmware.** Get your board's **kiss_modem** build from MeshCore's
releases (e.g. `RAK_4631_kiss_modem`), or use the MeshCore web flasher if it lists one for your board. For a
RAK4631: double-tap its reset button and copy the `.uf2` file onto the `RAK4631` drive that appears.
Then plug the radio into the Pi.

**2. On the Pi, run:**
```bash
git clone https://github.com/VeiledLink/meshcore-bot-starter ~/meshcore-bot-starter
cd ~/meshcore-bot-starter
./install.sh
```
The installer:
1. installs **meshcore-pi** (the MeshCore node software) and adds KISS radio support
2. asks your **bot settings**: name, channels, your own commands, and the radio and frequency
3. starts the node as a service (it starts at boot and restarts by itself)
4. installs **RemoteTerm**. Its installer asks a few questions, and `install.sh` tells you exactly what to answer.
5. sends your bot to RemoteTerm

**3. Try it:** send `test` in your test channel, or DM your bot `help`.
The web UI is at `http://<your-pi>.local:8000`.

## Setup B: companion radio over USB (about 10 minutes)

**1. The radio:** keep its normal **companion** firmware and settings. Set its name, frequency and channels
with the MeshCore app as usual. Then plug it into the Pi by USB. (Close the phone app's connection first:
only one app can talk to the radio at a time.)

**2. Install RemoteTerm** ([its README](https://github.com/jkingsman/Remote-Terminal-for-MeshCore)):
```bash
sudo apt-get install -y git curl && curl -LsSf https://astral.sh/uv/install.sh | sh && exec bash
git clone https://github.com/jkingsman/Remote-Terminal-for-MeshCore ~/Remote-Terminal-for-MeshCore
cd ~/Remote-Terminal-for-MeshCore && bash scripts/setup/install_service.sh
```
Answer: **Transport: 1 (Serial, auto-detect)** (or 2 to type the port, e.g. `/dev/ttyACM0`),
**Frontend: 2 (prebuilt)**, **Enable bots: y**, Basic Auth: your choice.

**3. Install the bot:**
```bash
git clone https://github.com/VeiledLink/meshcore-bot-starter ~/meshcore-bot-starter
cd ~/meshcore-bot-starter
python3 setup.py --bot          # bot name (same as the radio's name), channels, your own commands
python3 bot/deploy_bot.py       # sends the bot to RemoteTerm
```
Skip `install.sh` and the `meshcore-pi/` folder: those are only for Setup A.

**4. Try it:** send `test` in your test channel, or DM your bot `help`.

## Setup C: Station G3 with a Pi Zero 2 W (about 20 minutes)

The **Station G3** carries a Pi Zero 2 W as its computer: the Pi sits in the G3's 40-pin socket and talks to
the G3's SX1262 radio over SPI. The G3's 1 W amplifier boosts it to about 30 dBm.

**1. Hardware:** Pi Zero 2 W (with header) in the G3's MCU socket, **antenna on the G3**, power the G3 as B&Q
says (its board feeds the Pi). Flash Raspberry Pi OS Lite (64-bit) to the Pi's card first.

**2. On the Pi:** the same as Setup A:
```bash
git clone https://github.com/VeiledLink/meshcore-bot-starter ~/meshcore-bot-starter
cd ~/meshcore-bot-starter
./install.sh
```
When it asks **"Which radio?"**, answer **2 (Station G3)**. It then:
- writes the G3 radio config. The pin map is B&Q's official one (also used by Meshtastic): SPI0 CE0,
  **IRQ/DIO1 = GPIO 22, Busy = GPIO 24, Reset = GPIO 16**, DIO2 RF switch, DIO3 TCXO 1.8 V;
- turns on SPI and installs the radio library (LoRaRF, using Raspberry Pi OS's `rpi-lgpio`).
  If SPI was off, **reboot and run `./install.sh` again**;
- asks the **radio chip power: 19 dBm max**. That's the power going *into* the 1 W amplifier, not the antenna
  power. Lower it if the G3 sits near other radios.

**3. Try it:** send `test` in your test channel. Check the radio started: `journalctl -u meshcore-pi -n 30`.

Pin map source: B&Q Station G3 wiki (wiki.bqvoy.com/en/devkits/station-g3) and Meshtastic's
`lora-rpi-BQ-SG3-BQ35LORA900V1M-slot1.yaml`. **Not yet tested end to end with this kit**: if something doesn't
work, open an issue with the output of `journalctl -u meshcore-pi -n 50`.

## Changing things later

```bash
cd ~/meshcore-bot-starter
python3 setup.py --bot          # change bot settings or add/remove commands
python3 bot/deploy_bot.py       # send the updated bot (takes effect right away)
```
Changed the radio (frequency, power, port)? Run `python3 setup.py` (answer yes to the radio question), then
`sudo systemctl restart meshcore-pi`.

Your settings live in `bot/settings.json`, and you can edit that file directly instead of running setup.
To change how the bot *works* or add smarter commands, edit `bot/starter_bot.py`. It's short, plain Python. Then run
`python3 bot/deploy_bot.py` again.

## Your own commands

During setup, answer the "Your own commands" questions:
```
Command to add or change: rules
Reply for 'rules': Be kind, no spam. Welcome {name}!
```
`{name}` becomes the sender's name. Keep replies under ~100 characters so they fit in one mesh message.
Remove a command by entering `-rules`.

## Optional: alerts for your area

`alerts/feed_alerts.py` checks free public feeds every 3 minutes and posts anything new near you to a channel.
Turn each one on or off in `alerts/settings.json`:

| Alert | Source | Posts when | Example |
|---|---|---|---|
| Earthquakes | USGS | within `radius_mi`, at least `min_magnitude` | 🌎 Earthquake M3.1 10 km E of Chowchilla, CA (18 mi away) 7:12 PM |
| Weather | National Weather Service (US) | a new alert for your exact location | ⚠️ Heat Advisory: Merced until Wed 8 PM |
| Wildfires | National wildfire map (WFIGS) | a new fire within `fire_radius_mi`, at least `min_fire_acres` | 🔥 Oak Fire, Mariposa Co: 1,200 acres, 20% contained (25 mi away) |
| Air quality | AirNow (US) | your nearest area reaches `min_aqi` (151 = Unhealthy) | 😷 Air quality Unhealthy: AQI 162 (PM2.5) in Merced, CA |
| Rivers | NOAA river gauges | a gauge within `river_radius_mi` reaches flood stage | 🌊 Bear Creek at Merced: minor flooding, 12.5 ft |
| Space weather | NOAA | a geomagnetic storm of at least `min_kp` (7 = strong) | 🌌 Geomagnetic storm G3 (Kp 7): aurora possible, GPS/HF may be off |

```bash
cd ~/meshcore-bot-starter
cp alerts/settings.example.json alerts/settings.json
nano alerts/settings.json          # your lat/lon, channel, radius, and contact (NWS asks for one)
python3 alerts/feed_alerts.py --dry-run   # see what it would post right now
```
Add the channel (for example `#alerts`) in RemoteTerm first. Then run it every 3 minutes:
```bash
# if your username isn't "pi", change User= and the paths in feed-alerts.service first
sudo cp alerts/feed-alerts.service alerts/feed-alerts.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now feed-alerts.timer
```
The first run posts nothing: it only notes the alerts already out there, so a new install doesn't flood the
channel. Each alert is posted once (a fire once when it first shows up, air quality and storms at most once a day
per level).

Want more, like power outages, road incidents or evacuations? Those come from your state or utility, not a
national feed. Copy one of the `*_posts()` functions as a pattern. Most agencies publish free JSON feeds. Keep
posts short, and don't post more often than every few minutes.

## Updating

Pull the latest fixes and re-apply them:
```bash
cd ~/meshcore-bot-starter && git pull
meshcore-pi/patch_meshcore_pi.sh && sudo systemctl restart meshcore-pi
python3 bot/deploy_bot.py
```

## How it fits together

```
radio (KISS modem firmware) --USB--> meshcore-pi --TCP 5000--> RemoteTerm --> your bot
```
- **[meshcore-pi](https://github.com/brianwiddas/meshcore-pi)** is the MeshCore node: keys, encryption and
  routing all run on the Pi, and the radio is just a radio. `meshcore-pi/kissinterface.py` adds KISS radio
  support, and `meshcore-pi/patch_meshcore_pi.sh` adds it plus some crash fixes (listed at the top of the script).
- **[RemoteTerm](https://github.com/jkingsman/Remote-Terminal-for-MeshCore)** connects to the node like the
  MeshCore app does, gives you a web UI, and runs the bot code.
- **`bot/starter_bot.py`** is the bot. RemoteTerm keeps its own copy, and `deploy_bot.py` updates it.

| File | What |
|---|---|
| `install.sh` | One-time install (safe to run again) |
| `setup.py` | Setup questions; writes `bot/settings.json` and `~/meshcore-pi/config.toml` |
| `bot/starter_bot.py` | The bot |
| `bot/deploy_bot.py` | Sends the bot plus your settings to RemoteTerm |
| `meshcore-pi/` | KISS radio support, fixes, and an example config for doing it by hand |
| `tests/` | `python3 tests/test_bot.py` and `python3 tests/test_deploy.py` (no radio needed) |

## Troubleshooting

| Problem | Try |
|---|---|
| The bot never answers | `journalctl -u meshcore-pi -n 30`: does it say "KISS modem connected"? Check that the frequency settings match your mesh. |
| "could not open port" | Wrong radio picked, or the radio isn't on the KISS firmware. Run `ls /dev/serial/by-id/`, then `python3 setup.py`. |
| Replies in the web UI, but nobody hears them | Antenna, transmit power, or frequency settings. Are you in range of a repeater? |
| deploy says "Can't reach RemoteTerm" | `sudo systemctl status remoteterm` |
| deploy says bots are disabled | Re-run `bash ~/Remote-Terminal-for-MeshCore/scripts/setup/install_service.sh` and answer **y** to "Enable bots?" |
| Same name, but the identity changed after a reboot | `config.toml` lost its `privatekey` line. Run `python3 setup.py --save-key` right after a start. |

## Security

RemoteTerm's bots run Python on your Pi, so **anyone who can open the web UI can run code on the Pi.** Only use
it on a network you trust. Choose **Basic Auth** in RemoteTerm's installer (a login for the web page), or use a
firewall that only allows your own devices (e.g. via Tailscale). The node's port (5000) is set to
`127.0.0.1`, so only the Pi itself can reach it.

## License

MIT. See `LICENSE`. meshcore-pi, RemoteTerm and MeshCore are separate projects under their own licenses.
