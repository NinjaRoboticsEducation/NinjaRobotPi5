# Traditional Chinese font repair proposal

This is a prepared repair awaiting the project owner's managed-file approval.
It has not changed a driver or its authorization record.

The existing `pi5disp/src/pi5disp/fonts/NotoSansTC-Regular.otf` fails to load
because it contains an HTML error page. Its SHA-256 fingerprint (a content
identity check) is
`44b606dad683f7c1c8f5c95757ec4169e0f8876c4898e6045544bf97f8fdf835`.

Replace only that asset with the unmodified Noto Sans TC Regular font from
[the official, fixed upstream revision](https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/SubsetOTF/TC/NotoSansTC-Regular.otf).
The proposed file is 5,683,368 bytes; its SHA-256 is
`5bab0cb3c1cf89dde07c4a95a4054b195afbcfe784d69d75c340780712237537`.
Preserve the upstream [Open Font License](https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/LICENSE)
in the project notices and include the license with the packaged asset.
Adding that license to the driver package is part of this proposed approval.
The license file fingerprint is
`6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2`.

The download is staged outside the checkout at
`/tmp/ninja-font-review-ytl6nmo1`. Pillow (the image rendering library) loads it
as Noto Sans TC Regular. Representative Traditional Chinese text renders, and
each tested character differs from the missing-character fallback. This is a
software rendering check, not a physical display or complete character-coverage
test. The existing asset's load failure was reproduced without opening a display.

After approval, add a font-load regression test, run the display driver's suite
separately, confirm packaging includes the license, record the authorized hash
using the driver verifier, and rerun project gates. Preserve every driver API
(the calls used by other code) and all hardware control logic. Then check real
screen readability manually with the operator present.
