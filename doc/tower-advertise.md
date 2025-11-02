
# Tower Device Capability Advertisement Protocol

This document describes two compatible approaches for advertising device capabilities of Hardwario Tower nodes in compact MQTT messages. The first (preferred) is a human-readable text encoding. The second is a binary TLV encoded payload (Base64) and is provided as a backup option when message size or strict parsing requirements demand a more compact representation.

---

## Text-format discovery message (preferred)

### Example

`!13;L{991}l{K3}T[022021222324]F6`

### Packet format

- `!` — header character indicating text format (chosen to avoid confusion with Base64 binary payloads)
- Three characters indicating a semantic version, each representing major, minor and patch version numbers encoded as ASCII (`0x30 + n`). Example: `13;` represents version `v1.3.11`.
- Concatenated list of groups describing resources.

### Group format

- A single character (A–Z, a–z) identifying the resource type (see list below).
- Followed by one of:
  - A single hexadecimal digit or `-` indicating channel count (`-` = no channel, use `/-/` in MQTT topics).
  - A packed list enclosed in `{}` representing 3-bit values (two values per character: `ord = 0x30 + (n0 & 7) + 8*(n1 & 7)`). Trailing zeroes are trimmed after decoding.
  - A list of bus addresses enclosed in `[]`, represented as pairs of hex digits (e.g. `C2` → `12:2`).

### Decoding and usage

The decoder produces a dictionary that is passed to a Jinja2 template to generate Home Assistant discovery messages. Decoding is resource-agnostic: adding new entities requires only template updates.

Example decoded structure from `!L{991}l{K3}T[022021222324]F6`:

```python
resources = dict(
    L=dict(addr=[0,1,2,3,4], par=[1,1,1,1,1]),
    l=dict(addr=[0,1,2], par=[3,3,3]),
    T=dict(addr=["0:2","2:0","2:1","2:2","2:3","2:4"]),
    F=dict(addr=[0,1,2,3,4,5])
)
```

### Text-format: C producer (Hardwario Tower SDK compatible)

The following example shows how to construct and publish a text-format discovery message from a Hardwario Tower firmware using their SDK. It uses `twr_radio_pub_string()` to publish the message.

```c
#include <twr.h>
#include <stdio.h>

// Helper: append packed 3-bit values encoded as described in the spec
static void append_packed_3bit(char *buf, size_t *idx, const uint8_t *vals, size_t n)
{
    for (size_t i = 0; i < n; i += 2) {
        uint8_t a = vals[i] & 7;
        uint8_t b = (i + 1 < n) ? (vals[i + 1] & 7) : 0;
        buf[(*idx)++] = (char)(0x30 + a + (b << 3));
    }
}

void publish_text_discovery(const char *fw_version, const uint8_t *led_par, size_t led_n,
                            const uint8_t *led_addr, size_t led_addr_n)
{
    char buf[64];
    size_t idx = 0;

    // Header
    buf[idx++] = '!';
    // encode semantic version X Y Z as three ASCII chars: '0' + X etc.
    buf[idx++] = (char)('0' + 1); // major
    buf[idx++] = (char)('0' + 3); // minor
    buf[idx++] = ';';

    // Example: LED packed parameters
    buf[idx++] = 'L';
    buf[idx++] = '{';
    append_packed_3bit(buf, &idx, led_par, led_n);
    buf[idx++] = '}';

    // Example: LED bus addresses
    if (led_addr_n > 0) {
        buf[idx++] = 'T';
        buf[idx++] = '[';
        for (size_t i = 0; i < led_addr_n; ++i) {
            // represent each address as two hex chars
            unsigned int a = led_addr[i] >> 4;
            unsigned int b = led_addr[i] & 0x0F;
            buf[idx++] = "0123456789ABCDEF"[a];
            buf[idx++] = "0123456789ABCDEF"[b];
        }
        buf[idx++] = ']';
    }

    buf[idx] = '\0';

    // publish using Hardwario SDK radio API
    twr_radio_pub_string("home/tower/caps", buf);
}
```

### Text-format: Python parser (consumer)

Example parser for the text-format discovery message. It decodes the groups and reconstructs arrays of addresses and parameter lists.

```python
def parse_text_discovery(msg: str):
    # msg example: '!13;L{991}l{K3}T[022021222324]F6'
    if not msg or msg[0] != '!':
        raise ValueError('Unsupported format')

    pos = 1
    # read semantic version until ';'
    ver = ''
    while pos < len(msg) and msg[pos] != ';':
        ver += msg[pos]
        pos += 1
    pos += 1

    resources = {}

    while pos < len(msg):
        tag = msg[pos]; pos += 1
        if pos >= len(msg):
            break
        ch = msg[pos]
        if ch == '{':
            # packed 3-bit values until '}'
            pos += 1
            vals = []
            while pos < len(msg) and msg[pos] != '}':
                code = ord(msg[pos]) - 0x30
                low = code & 7
                high = (code >> 3) & 7
                vals.append(low)
                vals.append(high)
                pos += 1
            # trim trailing zeros
            while vals and vals[-1] == 0:
                vals.pop()
            pos += 1
            resources[tag] = {'par': vals, 'addr': list(range(len(vals)))}
        elif ch == '[':
            # list of bus addresses until ']'
            pos += 1
            addrs = []
            while pos + 1 < len(msg) and msg[pos] != ']':
                a = int(msg[pos], 16)
                b = int(msg[pos+1], 16)
                addrs.append(f"{a}:{b}")
                pos += 2
            pos += 1
            resources[tag] = {'addr': addrs}
        else:
            # single hex digit or '-'
            pos += 1
            if ch == '-':
                resources[tag] = {'addr': ['-']}
            else:
                n = int(ch, 16)
                resources[tag] = {'addr': list(range(n))}

    return {'version': ver, 'resources': resources}

```

### Resource entity mapping

| Letter | Entity type                     |
|--------|---------------------------------|
| `L`    | LED — PWM (1–4 channels)        |
| `l`    | LED — addressable (1–4 channels)|
| `F`    | Fan (PWM)                       |
| `T`    | Temperature sensor †            |
| `H`    | Humidity sensor †               |
| `B`    | Barometer (pressure) †          |
| `I`    | Illuminance sensor †            |
| `C`    | CO₂ sensor †                    |
| `V`    | Battery (4-cell, 6V) †          |
| `v`    | Mini battery (2-cell, 3V) †     |

† indicates a standard Hardwario Tower sensor.

---

## Binary TLV + Base64 (backup)

This compact binary encoding packs a TLV (Type-Length-Value) structure and then encodes it with Base64. Use this when messages must be shorter or machine parsing is preferred. Consider this a fallback if the text encoding runs into Tower message length limits.

### Message structure

- Version (1 byte)
- Entry Count (1 byte)
- Entries: repeated
  - Type (1 byte)
  - Length (1 byte)
  - Value (Length bytes)

### Entry types (examples)

| Type | Tag | Value format |
|------|-----|--------------|
| 0x01 | LED | 16×4-bit sub-channel counts (packed two per byte) |
| 0x02 | FAN | 1 byte: fan count |
| 0x03 | TS  | M×1 byte: temp sensors (4b bus | 4b instance) |
| 0x04 | H   | K×1 byte: humidity sensors (bus | inst) |
| 0x05 | WL  | L×1 byte: water level sensors (bus | inst) |
| 0x0F | —   | Reserved |

### C firmware example (producer)

```c
#include <stdint.h>
#include <string.h>
// Include or implement a Base64 encoder

#define MAX_ENTRIES 5

void advertise_caps(
    const char *fw_version,
    const uint8_t led_sub[16],
    uint8_t fan_count,
    const uint8_t temp_bus[16],
    const uint8_t temp_inst[16],
    uint8_t humidity_count,
    const uint8_t hum_bus[],
    const uint8_t hum_inst[])
{
    uint8_t buf[64];
    size_t idx = 0;

    // Header
    buf[idx++] = 1;            // Version
    buf[idx++] = 4;            // Number of TLV entries

    // LEDs (Type=0x01)
    buf[idx++] = 0x01;
    buf[idx++] = 16;
    for (int i = 0; i < 16; i += 2) {
        buf[idx++] = (led_sub[i] << 4) | (led_sub[i+1] & 0x0F);
    }

    // Fans (Type=0x02)
    buf[idx++] = 0x02;
    buf[idx++] = 1;
    buf[idx++] = fan_count;

    // Temp sensors (Type=0x03)
    buf[idx++] = 0x03;
    buf[idx++] = 16;
    for (int i = 0; i < 16; i++) {
        buf[idx++] = ((temp_bus[i] & 0x0F) << 4) | (temp_inst[i] & 0x0F);
    }

    // Humidity sensors (Type=0x04)
    buf[idx++] = 0x04;
    buf[idx++] = humidity_count;
    for (int i = 0; i < humidity_count; i++) {
        buf[idx++] = ((hum_bus[i] & 0x0F) << 4) | (hum_inst[i] & 0x0F);
    }

    // Base64 encode
    char payload[64];
    size_t payload_len = base64_encode(buf, idx, payload);
    payload[payload_len] = '\0';

    // Publish via MQTT
    twr_radio_pub_string("caps/set", payload);
}
```

### Python parsing example (consumer)

```python
import base64

def parse_caps(payload_b64):
    data = base64.b64decode(payload_b64)
    version = data[0]
    count   = data[1]
    pos = 2
    info = {'version': version}

    for _ in range(count):
        t = data[pos]; l = data[pos+1]; pos += 2
        v = data[pos:pos+l]; pos += l

        if t == 0x01:
            led = []
            for b in v:
                led.extend([b >> 4, b & 0x0F])
            info['led_subchannels'] = led
        elif t == 0x02:
            info['fan_count'] = v[0]
        elif t == 0x03:
            info['temperature_sensors'] = [(b>>4, b&0x0F) for b in v]
        elif t == 0x04:
            info['humidity_sensors'] = [(b>>4, b&0x0F) for b in v]
        else:
            info[f'type_{t}'] = v
    return info
```

## Extensibility and recommendations

- Prefer the text-format discovery message for readability and easy template-driven generation.
- Use the binary TLV + Base64 encoding as a compact fallback when message length is a concern.
- When adding new features, add a new TLV type and update the Jinja2 templates accordingly.

---

*End of documentation.*