r"""A235 — `panel()` gained an axis band, and `box()` must not have noticed.

Marc's v18 asked the KPI row for a chart no entry point drew: *"Histogram and Box-Whisker
x-axis have to be aligned"* AND *"an x-axis with labels"*. `panel()` had the shared scale and
no labels; `box()` had the labels and reads no bin column at all. A235 moved the placement rule
(`_LabelBands`) and the strategy table (`_axis_ticks`) out of `box()`'s body so both entry
points read ONE copy — because a second copy of a collision rule drifts invisibly: two charts
that disagree about which labels fit still both look fine.

## The instrument failures this file was written against

- **R-843** — a pin is only a pin if the break moves it. The identity test below is calibrated:
  `test_THE_IDENTITY_COMPARISON_CAN_ACTUALLY_FAIL` stages two breaks and confirms it goes red.
  Without that, "0 differences" is equally consistent with a comparison that compares nothing.
- **R-2254** — an empty collection is not a pass. Every loop here asserts its own corpus is
  non-empty before asserting anything about its contents.
- **R-2260** — a substring is not a rule. The label assertions parse `<text>` elements out of
  the SVG rather than searching it for digits, which appear in coordinates on every line.
- **R-855** — the picture caught what reading could not. The clipping test exists because a
  raster showed `)` where `0` belonged while the DOM held a correct, present `<text>` element.
"""
import hashlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

from lib import distribution as d                                          # noqa: E402

STRATEGIES = (d.TICK_PERCENTILES, d.TICK_BOUNDS, d.TICK_NONE, d.TICK_EXTREMES)


def _row(**over):
    """A distribution row carrying every column the three entry points read."""
    base = dict(p25=17.0, p50=20.0, p75=24.0, whisker_lo=10.0, whisker_hi=31.0,
                min_value=3.0, max_value=38.0, outlier_count=2, n=75,
                bin_min=0.0, bin_max=80.0, bin_incr=8.0,
                bin_counts="1,2,5,9,14,18,12,8,4,2",
                below_min_count=0, above_max_count=0)
    base.update(over)
    return base


def _texts(svg: str) -> list:
    """The label strings actually emitted, parsed rather than grepped (R-2260)."""
    return re.findall(r"<text[^>]*>([^<]*)</text>", svg)


# ── The extraction is inert ─────────────────────────────────────────────────────────────────

SHAPES = {
    "plain": {},
    "flat":  dict(p25=0.0, p50=0.0, p75=0.0, whisker_lo=0.0, whisker_hi=0.0,
                  min_value=0.0, max_value=0.0),
    "wide":  dict(p25=320.0, p50=377.0, p75=448.0, whisker_lo=300.0, whisker_hi=460.0,
                  min_value=290.0, max_value=470.0, bin_min=250.0, bin_max=500.0),
    "tight": dict(p25=1.1, p50=1.2, p75=1.3, whisker_lo=1.0, whisker_hi=1.4,
                  min_value=1.0, max_value=1.5),
    "noext": dict(min_value=None, max_value=None),
}

# 🚨 EVERY HASH BELOW WAS GENERATED FROM `box()` AT `a7e1f78` — THE COMMIT THIS ROUND BRANCHED
# FROM — AND THE GENERATOR REPORTED 0 MISMATCHES AGAINST THE POST-EXTRACTION MODULE OVER ALL
# 240. A235's report also carries the wider run: 11,520 renders across five row shapes, four
# tick strategies, three widths and every boolean flag, byte-identical.
#
# ⚠️ A HASH IS NOT A SECOND IMPLEMENTATION, WHICH IS WHY THIS IS A FIXTURE AND THE MODULE IS
# NOT. A hand-written "expected SVG" would be a second renderer that drifts; a fingerprint can
# only agree with output it was taken from.
#
# 🚨 AND IT DELIBERATELY DOES NOT READ GIT. The first draft loaded `a7e1f78:site/lib/
# distribution.py` with `git show` and skipped when that failed. **`lint-and-test` in `ci.yml`
# checks out at the default `fetch-depth: 1`**, so that test would have passed locally and
# SKIPPED SILENTLY IN CI — a guard that is green everywhere and asserting nothing where it
# matters, which is the exact shape R-575's manifest skips cost this project four tests.
_BOX_GOLDENS = {
    "flat|percentiles|120|0|0": "9c80ee2b5e22d3bd7a9850d18f270e36",
    "flat|percentiles|120|0|1": "6a4c22557d8667e745292c65905303d1",
    "flat|percentiles|120|1|0": "4ab5f16786103def09b991625214bc5e",
    "flat|percentiles|120|1|1": "896c6ba564a887e1374da56b47719007",
    "flat|percentiles|240|0|0": "fbd81aea1631b001e2cc2cf54bffbe5a",
    "flat|percentiles|240|0|1": "3f0d816afd1f5000af66b309ab0346d4",
    "flat|percentiles|240|1|0": "3e6d8c85b5ec04cb134bc3571c003924",
    "flat|percentiles|240|1|1": "cd82f747eb7fa3e8257d758bb642214d",
    "flat|percentiles|448|0|0": "dfd304a59eaebb316744dc71fffa0dbd",
    "flat|percentiles|448|0|1": "0438ae477a5529ce3265d36098497d1a",
    "flat|percentiles|448|1|0": "0239bf2b7b27cf39d796928fe6330883",
    "flat|percentiles|448|1|1": "b014aa110189117618a2cd9fc3dddbfb",
    "flat|bounds|120|0|0": "9c80ee2b5e22d3bd7a9850d18f270e36",
    "flat|bounds|120|0|1": "6a4c22557d8667e745292c65905303d1",
    "flat|bounds|120|1|0": "4ab5f16786103def09b991625214bc5e",
    "flat|bounds|120|1|1": "896c6ba564a887e1374da56b47719007",
    "flat|bounds|240|0|0": "fbd81aea1631b001e2cc2cf54bffbe5a",
    "flat|bounds|240|0|1": "3f0d816afd1f5000af66b309ab0346d4",
    "flat|bounds|240|1|0": "3e6d8c85b5ec04cb134bc3571c003924",
    "flat|bounds|240|1|1": "cd82f747eb7fa3e8257d758bb642214d",
    "flat|bounds|448|0|0": "dfd304a59eaebb316744dc71fffa0dbd",
    "flat|bounds|448|0|1": "0438ae477a5529ce3265d36098497d1a",
    "flat|bounds|448|1|0": "0239bf2b7b27cf39d796928fe6330883",
    "flat|bounds|448|1|1": "b014aa110189117618a2cd9fc3dddbfb",
    "flat|none|120|0|0": "244c5d2ff8d9f13f267853fd57771e3a",
    "flat|none|120|0|1": "8b65254fc9df03c318fd4459695498d5",
    "flat|none|120|1|0": "1a47f12c28bcfd4ad0f6ecdb2794ee56",
    "flat|none|120|1|1": "161e23c0ae153f802a493f712c95ccaa",
    "flat|none|240|0|0": "f6d362150ef58c88002f7decf31dd7f9",
    "flat|none|240|0|1": "8969bf463da57a683d86c298de9945be",
    "flat|none|240|1|0": "4f953df30d97deaf6263cd7887315224",
    "flat|none|240|1|1": "2bafbf2cde97f3c419aa6ba261edd919",
    "flat|none|448|0|0": "37fdf3b6d6f9bce2c3bc99d4fb29da13",
    "flat|none|448|0|1": "643aad51868d4e1886e53d510288935d",
    "flat|none|448|1|0": "33d61374912f320088e5a6060ba7b9a8",
    "flat|none|448|1|1": "1c47ac2f32963699c3ebab8df3deebd8",
    "flat|extremes|120|0|0": "9c80ee2b5e22d3bd7a9850d18f270e36",
    "flat|extremes|120|0|1": "6a4c22557d8667e745292c65905303d1",
    "flat|extremes|120|1|0": "4ab5f16786103def09b991625214bc5e",
    "flat|extremes|120|1|1": "896c6ba564a887e1374da56b47719007",
    "flat|extremes|240|0|0": "fbd81aea1631b001e2cc2cf54bffbe5a",
    "flat|extremes|240|0|1": "3f0d816afd1f5000af66b309ab0346d4",
    "flat|extremes|240|1|0": "3e6d8c85b5ec04cb134bc3571c003924",
    "flat|extremes|240|1|1": "cd82f747eb7fa3e8257d758bb642214d",
    "flat|extremes|448|0|0": "dfd304a59eaebb316744dc71fffa0dbd",
    "flat|extremes|448|0|1": "0438ae477a5529ce3265d36098497d1a",
    "flat|extremes|448|1|0": "0239bf2b7b27cf39d796928fe6330883",
    "flat|extremes|448|1|1": "b014aa110189117618a2cd9fc3dddbfb",
    "noext|percentiles|120|0|0": "91c1b405abc4f21a44c985e68f2c4094",
    "noext|percentiles|120|0|1": "5c55cac9568f7fd43c0fa53132d7499d",
    "noext|percentiles|120|1|0": "079bbfb4105ad28355b109018580f4df",
    "noext|percentiles|120|1|1": "4c80639cfb8fb2c18484b12178dc372c",
    "noext|percentiles|240|0|0": "d66401fb1d3fa924e2eab7093231b4eb",
    "noext|percentiles|240|0|1": "89a7aa17164a09f0d581970cbbb3881d",
    "noext|percentiles|240|1|0": "9df4405c053eeb9279bc7129bc6f29ff",
    "noext|percentiles|240|1|1": "80bfb0fa0f24865e299550411a8d7725",
    "noext|percentiles|448|0|0": "86f3387bd5e71505387b0a77815ef429",
    "noext|percentiles|448|0|1": "4a83003a670a27d7f4de77567304da55",
    "noext|percentiles|448|1|0": "dcee279ccc85c596fd548f920fa92a0a",
    "noext|percentiles|448|1|1": "09f91a7f671362d0078d0eb915e7f8f7",
    "noext|bounds|120|0|0": "a432fe57f7bda5fbe00ab0e69bd2ec52",
    "noext|bounds|120|0|1": "29fc0d8c7166922c39371f1306ba95fc",
    "noext|bounds|120|1|0": "b6c5025f4206b01c101d32567689a30d",
    "noext|bounds|120|1|1": "d9acbdb0b479fe41b12919767550f80e",
    "noext|bounds|240|0|0": "9d31d56a2b9ec4378b038453153e1da6",
    "noext|bounds|240|0|1": "89db984b92ad353bb513897cee890b19",
    "noext|bounds|240|1|0": "833565d239db80821f3d9abe540f3ce0",
    "noext|bounds|240|1|1": "f081c12bbbf92d0d7bcb6f339483e7a4",
    "noext|bounds|448|0|0": "f5d4845118e2dcbfc0b87113f023a711",
    "noext|bounds|448|0|1": "e098d7ed983d0d3727dc8b921d653aa5",
    "noext|bounds|448|1|0": "dd83d46748de2374cc53349d8acc4e75",
    "noext|bounds|448|1|1": "c8d5bf003f906d7eb1555aa6dc34c4ac",
    "noext|none|120|0|0": "59ce8abd4b1a4a626e2383ea593d0847",
    "noext|none|120|0|1": "ce0bbeabf6c9664a90fb630a13f56371",
    "noext|none|120|1|0": "29330b45b2476e6868e965dd872ce303",
    "noext|none|120|1|1": "72a41808db005c89b9a0c825b2bb4939",
    "noext|none|240|0|0": "bf589368c78555b4fb94f95724aa8c97",
    "noext|none|240|0|1": "e08ed071f56aff06d3f3be4cac08b6e3",
    "noext|none|240|1|0": "e5862aac1cb373a320b4bec226395a1d",
    "noext|none|240|1|1": "1b20b3adc592eccb0e36b1f5dfe0f390",
    "noext|none|448|0|0": "f06867dc6309ed4cdb21e0546d44a4b3",
    "noext|none|448|0|1": "72e1ba0997a44095238595c060d3c821",
    "noext|none|448|1|0": "c7f3f72e23dd25350953ec9ab387fd13",
    "noext|none|448|1|1": "4a7f3e90f30e709ff15796eecb520285",
    "noext|extremes|120|0|0": "7ba6638fbf37d1585a0a7bfeb833af08",
    "noext|extremes|120|0|1": "0c0a5d43d658e0d455bbf7cd0bc7cbdc",
    "noext|extremes|120|1|0": "2a8bea13c04c60ece18ed39c62793495",
    "noext|extremes|120|1|1": "e8d4e2a7fc82a20c805b36c065edb714",
    "noext|extremes|240|0|0": "364a94d36a7f116c909a7b550426e8e0",
    "noext|extremes|240|0|1": "c6228fbb0461944e49e288542b57faca",
    "noext|extremes|240|1|0": "a29958606397f71f5eb95ed6f84454dd",
    "noext|extremes|240|1|1": "e4ece42990cfe1160d0fd6379454574b",
    "noext|extremes|448|0|0": "49df80dba854cdf6b33ddd068e23b39b",
    "noext|extremes|448|0|1": "255a2d72536de7abd52365ef8bfce634",
    "noext|extremes|448|1|0": "cf871c472ba868f718d4a15a1151530f",
    "noext|extremes|448|1|1": "32fe86803381f9dee72dde2074017a4e",
    "plain|percentiles|120|0|0": "1cc9a316d0275c10829fedff309a40e7",
    "plain|percentiles|120|0|1": "d2459eca1d3903520bb04eb702715a29",
    "plain|percentiles|120|1|0": "3b3de5f9552fd658ef35457cd16c8cdd",
    "plain|percentiles|120|1|1": "16fd5a15bb8cf0b26a44413a4b65dddb",
    "plain|percentiles|240|0|0": "39a14ff8ec5778e9fe74fed7b98a4584",
    "plain|percentiles|240|0|1": "a02f0a6cd461fe353714b598d8596afa",
    "plain|percentiles|240|1|0": "100a94610a29524c71af28c76f959613",
    "plain|percentiles|240|1|1": "4307a2684f5059e5b7e09b6ba1d2d115",
    "plain|percentiles|448|0|0": "12cd03062e2cc8b331bfc64d27e35ea8",
    "plain|percentiles|448|0|1": "22eab5b0b4c6475098c4f7638e869736",
    "plain|percentiles|448|1|0": "49141bf1d30bdd3d103247d38c69ae16",
    "plain|percentiles|448|1|1": "a98aaea9718e19e9c48a631160aa926b",
    "plain|bounds|120|0|0": "67fa0dcb6eeb470626f9db5992783583",
    "plain|bounds|120|0|1": "dca18df65a6fa6a22895499722d96dcd",
    "plain|bounds|120|1|0": "dd44f2eb7491a4427f9b14f7b7a584c0",
    "plain|bounds|120|1|1": "ceb15c7292974ac7972aded090319103",
    "plain|bounds|240|0|0": "59fa27ea7fed3f8e1308f2c0be43e9d8",
    "plain|bounds|240|0|1": "a054eb7eb671ed5f6a060f0de478f618",
    "plain|bounds|240|1|0": "88d4cdbb2c916f6c83a0753430caf58d",
    "plain|bounds|240|1|1": "c3f60efb7a502e6c7acac2462ab233a8",
    "plain|bounds|448|0|0": "c40248d1b0db68335ec5377496f5edaf",
    "plain|bounds|448|0|1": "c8e36c7b10d7ab5cb86be5b47bd22e00",
    "plain|bounds|448|1|0": "ac6a92af08d92d6aaa65c3e2fe2ac651",
    "plain|bounds|448|1|1": "b971f4b7784dc77260e1400c1cf17535",
    "plain|none|120|0|0": "02e15dde08942067127636e619f400a7",
    "plain|none|120|0|1": "b9e931d2bb63400fdebadd74dec6fb9c",
    "plain|none|120|1|0": "2929465ab8e8af0266b1658004c11bc6",
    "plain|none|120|1|1": "373e49993bb084074aac05d51675a9a6",
    "plain|none|240|0|0": "7739e18674bd7dc67742e89dd13ddf5b",
    "plain|none|240|0|1": "3d0c74fe1198770d76b10aa0de6bda22",
    "plain|none|240|1|0": "272141399f940c6dc96a62209a597dbf",
    "plain|none|240|1|1": "26eaf972466688e19988b0d7222c868b",
    "plain|none|448|0|0": "f25d3e56a078ef5c5525cdad8447c1e4",
    "plain|none|448|0|1": "fb81fd71597cc83c827412963f59fbda",
    "plain|none|448|1|0": "95872186ba656a967a74ae7104c1997e",
    "plain|none|448|1|1": "53a68c5f1730ff6fa6e66cdb3ddf0219",
    "plain|extremes|120|0|0": "48e505bee4194d9c84f9fe42019c55c1",
    "plain|extremes|120|0|1": "bd5e75a88a8d778d37313bf43bba4a56",
    "plain|extremes|120|1|0": "618a4cf31faa5a399163472e91684a4d",
    "plain|extremes|120|1|1": "8026119fc74496b9dfd914c4dbb6684f",
    "plain|extremes|240|0|0": "6b47cba6ff782ef3c4266d5737f8690b",
    "plain|extremes|240|0|1": "6355a2dcdf7a721124dcc38505b59d8d",
    "plain|extremes|240|1|0": "49fc35d9d2d40b06ffba52436b877eff",
    "plain|extremes|240|1|1": "06efe8b0e3b600ef3f9cb89dc426c3e5",
    "plain|extremes|448|0|0": "f9f03b7566cd42c94c1b69190f69b2e6",
    "plain|extremes|448|0|1": "09e38d94ec6ff0143463a45ca7542991",
    "plain|extremes|448|1|0": "e75bcc2d2ce58a9a568739dc8062b6c6",
    "plain|extremes|448|1|1": "314eae3d2eafb3ad087395d084058d28",
    "tight|percentiles|120|0|0": "22793dc1eadbcb8f24fa84ae71cb2cfb",
    "tight|percentiles|120|0|1": "1974817600d6b94f503e7e7feb56baf1",
    "tight|percentiles|120|1|0": "02b9ef1313a81683db14cde5ff5b8591",
    "tight|percentiles|120|1|1": "039193b1dc5778f01e85785848a3420f",
    "tight|percentiles|240|0|0": "edfbe5809075c57a40a148a617687e5d",
    "tight|percentiles|240|0|1": "882c75e13543b946645a2f0c19c2298d",
    "tight|percentiles|240|1|0": "81d2a0ea2d997e52e886ce59dff7d5bb",
    "tight|percentiles|240|1|1": "3e995654d39d10327a62b6290de3ed08",
    "tight|percentiles|448|0|0": "2407cd157569c90948ac826b68c1328a",
    "tight|percentiles|448|0|1": "da78b528e721cca209d0f5536bc18ea0",
    "tight|percentiles|448|1|0": "2f1bff8136abf78b6fb2cb6174fe372a",
    "tight|percentiles|448|1|1": "a9a6ab17e94912b4b4d8edbcf231e9a9",
    "tight|bounds|120|0|0": "22793dc1eadbcb8f24fa84ae71cb2cfb",
    "tight|bounds|120|0|1": "1974817600d6b94f503e7e7feb56baf1",
    "tight|bounds|120|1|0": "02b9ef1313a81683db14cde5ff5b8591",
    "tight|bounds|120|1|1": "039193b1dc5778f01e85785848a3420f",
    "tight|bounds|240|0|0": "edfbe5809075c57a40a148a617687e5d",
    "tight|bounds|240|0|1": "882c75e13543b946645a2f0c19c2298d",
    "tight|bounds|240|1|0": "81d2a0ea2d997e52e886ce59dff7d5bb",
    "tight|bounds|240|1|1": "3e995654d39d10327a62b6290de3ed08",
    "tight|bounds|448|0|0": "2407cd157569c90948ac826b68c1328a",
    "tight|bounds|448|0|1": "da78b528e721cca209d0f5536bc18ea0",
    "tight|bounds|448|1|0": "2f1bff8136abf78b6fb2cb6174fe372a",
    "tight|bounds|448|1|1": "a9a6ab17e94912b4b4d8edbcf231e9a9",
    "tight|none|120|0|0": "f9046cf885da36e5449e8414192e3224",
    "tight|none|120|0|1": "cdaaedec32f19157f67212ac14247fd3",
    "tight|none|120|1|0": "3435dd0f6057a84b48b3a3bcc57c1387",
    "tight|none|120|1|1": "68179b427bce0422a5069937ab726f6a",
    "tight|none|240|0|0": "9db3a44ef1eeb30b6bac4326ab668d87",
    "tight|none|240|0|1": "02635c44d7083e4b74d448d0bdce6b96",
    "tight|none|240|1|0": "2d1b4af8bcc32e2f658bb8bc78e12232",
    "tight|none|240|1|1": "0cb717258d49750b7bcaafdf41bd5244",
    "tight|none|448|0|0": "2c0b18368268c28b714664d2699ba590",
    "tight|none|448|0|1": "b135f053d581433aa1e77537862c9a21",
    "tight|none|448|1|0": "17ff99c300bce285aca29f5b9ed27ace",
    "tight|none|448|1|1": "53f578d06c3c59b50dbf8ceef95d3b4f",
    "tight|extremes|120|0|0": "22793dc1eadbcb8f24fa84ae71cb2cfb",
    "tight|extremes|120|0|1": "1974817600d6b94f503e7e7feb56baf1",
    "tight|extremes|120|1|0": "02b9ef1313a81683db14cde5ff5b8591",
    "tight|extremes|120|1|1": "039193b1dc5778f01e85785848a3420f",
    "tight|extremes|240|0|0": "edfbe5809075c57a40a148a617687e5d",
    "tight|extremes|240|0|1": "882c75e13543b946645a2f0c19c2298d",
    "tight|extremes|240|1|0": "81d2a0ea2d997e52e886ce59dff7d5bb",
    "tight|extremes|240|1|1": "3e995654d39d10327a62b6290de3ed08",
    "tight|extremes|448|0|0": "2407cd157569c90948ac826b68c1328a",
    "tight|extremes|448|0|1": "da78b528e721cca209d0f5536bc18ea0",
    "tight|extremes|448|1|0": "2f1bff8136abf78b6fb2cb6174fe372a",
    "tight|extremes|448|1|1": "a9a6ab17e94912b4b4d8edbcf231e9a9",
    "wide|percentiles|120|0|0": "50d2b2b9abdc99f73c3d1fe38b7cfecb",
    "wide|percentiles|120|0|1": "5886d1312482889b1f2371d1ccdec41a",
    "wide|percentiles|120|1|0": "b4df7565283656ae3a09840bd0b27201",
    "wide|percentiles|120|1|1": "40da84fa07dc061dc77d7419ea564d8a",
    "wide|percentiles|240|0|0": "da302ecc49c4c109c1d865f4d3d58fe8",
    "wide|percentiles|240|0|1": "f5122bd14a5502e50eee4579b9dc9c48",
    "wide|percentiles|240|1|0": "161db6077b6cd40fcfd426c0834860f5",
    "wide|percentiles|240|1|1": "1fdf854816fb05adf8544a7c10b66faa",
    "wide|percentiles|448|0|0": "401073638b7bcc48f5e89a98972491e3",
    "wide|percentiles|448|0|1": "88b581a0842fb7b830e2db6c763cc96c",
    "wide|percentiles|448|1|0": "5b5bafb0bbad4a0e41a9d463d0160fbf",
    "wide|percentiles|448|1|1": "7b272a093bfbc1ef66a8318cd43007a0",
    "wide|bounds|120|0|0": "50d2b2b9abdc99f73c3d1fe38b7cfecb",
    "wide|bounds|120|0|1": "5886d1312482889b1f2371d1ccdec41a",
    "wide|bounds|120|1|0": "b4df7565283656ae3a09840bd0b27201",
    "wide|bounds|120|1|1": "40da84fa07dc061dc77d7419ea564d8a",
    "wide|bounds|240|0|0": "5ea0a6cda8273f2924b6acf23e6a8c9d",
    "wide|bounds|240|0|1": "b02ff228a4fb5fc7d25f50ab6ebaafdc",
    "wide|bounds|240|1|0": "6c09bd4b740b4755bc13ecece3d26ae4",
    "wide|bounds|240|1|1": "510ae08e3515b43699dac9ed2dfc4d6b",
    "wide|bounds|448|0|0": "4d2b54dc8f35508f75c69ceab24c2ea6",
    "wide|bounds|448|0|1": "917dc62b66e6e704148bbc45d0743c95",
    "wide|bounds|448|1|0": "bd0cc2d4c937d64b25e495030cfc094e",
    "wide|bounds|448|1|1": "6d8654573c901550c0a44baff6d52741",
    "wide|none|120|0|0": "6d347164206e5ff2f3dfd24d5ff67aed",
    "wide|none|120|0|1": "8723fb0968d6022bb54dc06e370b5d97",
    "wide|none|120|1|0": "0d17701a5d1e3810f36fca8ec0caeaeb",
    "wide|none|120|1|1": "e2994a8c8e8f04dbc8ad327ae082c19a",
    "wide|none|240|0|0": "53f4a86dbc8206d22e9f8f997afdb94c",
    "wide|none|240|0|1": "b59888c5ef2b4a2f42c3a35d236141ca",
    "wide|none|240|1|0": "dcfc4554e609085337d1c1e2f8bbd653",
    "wide|none|240|1|1": "5c914ad914f5e69b6f1ea46be0e0d643",
    "wide|none|448|0|0": "3f5e141115601d4fbe85a6c42002a28e",
    "wide|none|448|0|1": "1e6fa61241f067f6a503e0e100da8ef8",
    "wide|none|448|1|0": "c3e326748de51f657a5b9316ba8e6871",
    "wide|none|448|1|1": "af70f1d1f67cb8cf31d5119659eea63f",
    "wide|extremes|120|0|0": "c2ba389aee6a1e78f87e37cc9d879767",
    "wide|extremes|120|0|1": "c72cb912f843df8f40aa5aa7df53b940",
    "wide|extremes|120|1|0": "ae9710c6c12be28e12f4cc288cb9760c",
    "wide|extremes|120|1|1": "d3ab587660cb14fa590f7d0800557694",
    "wide|extremes|240|0|0": "288d8448caa910f59674d75fc1465cac",
    "wide|extremes|240|0|1": "c5fbe0d337b02514152270163bc495de",
    "wide|extremes|240|1|0": "9be5c71484790893a9cbeaf682055cb3",
    "wide|extremes|240|1|1": "9efccca6a684ce14818d737747e4ae73",
    "wide|extremes|448|0|0": "84a244edf6f8f0f2cea397f6cf0a22fb",
    "wide|extremes|448|0|1": "8be9e254faceca59d6ac8b5ad74210c8",
    "wide|extremes|448|1|0": "7d7fe865c0eaa5fd251d82b62a4edf41",
    "wide|extremes|448|1|1": "652d5de00b7e274eba4b3582d9079ef3",
}


def _probe(shape: str, ticks: str, width: int, two: bool, own: bool):
    kw = dict(width=width, ticks=ticks, value=35.0, value_labels_own_row=own,
              outliers=True, metric="total_yards")
    if two:
        kw["value_below"] = 22.0
    return _row(**SHAPES[shape]), kw


def test_THE_BOX_EXTRACTION_CHANGED_NOT_ONE_BYTE():
    """🚨 `_LabelBands` AND `_axis_ticks` CAME OUT OF `box()`'s BODY, AND `box()` HAS ~130 TESTS
    AND EVERY LIVE CALL SITE ON THE SITE. The extraction is only safe if it is INERT.

    ⚠️ THIS ALSO OUTLIVES THE REFACTOR. After A235 it is a golden-output test on `box()`: any
    later round that changes how a label is placed or which ticks a strategy emits gets a red
    test naming the exact combination, rather than discovering it on a page.
    """
    assert len(_BOX_GOLDENS) == 240, (
        f"the golden set is {len(_BOX_GOLDENS)} entries, not 240 — it was edited rather than "
        f"regenerated (R-2254: a shrunken corpus still passes)")
    changed = []
    for key, digest in _BOX_GOLDENS.items():
        shape, ticks, width, two, own = key.split("|")
        row, kw = _probe(shape, ticks, int(width), two == "1", own == "1")
        actual = hashlib.md5(d.box(row, **kw).encode()).hexdigest()
        if actual != digest:
            changed.append(key)
    assert not changed, (
        f"{len(changed)} of {len(_BOX_GOLDENS)} box() renders changed: {changed[:5]}. "
        f"Label placement or the tick strategy moved.")


def test_THE_GOLDEN_COMPARISON_CAN_ACTUALLY_FAIL(monkeypatch):
    """🚨 R-843. `0 changed` is also what a comparison that compares nothing reports.

    Two breaks, each aimed at one of the two things extracted: the collision constant
    `_LabelBands` reads, and the priority ORDER `_axis_ticks` returns — which is Marc's own
    (*"label MIN, Max, 25pctl, 75pctl where there is room"*) and decides which labels survive
    when they cannot all fit.
    """
    def changed() -> int:
        n = 0
        for key, digest in _BOX_GOLDENS.items():
            shape, ticks, width, two, own = key.split("|")
            row, kw = _probe(shape, ticks, int(width), two == "1", own == "1")
            if hashlib.md5(d.box(row, **kw).encode()).hexdigest() != digest:
                n += 1
        return n

    assert changed() == 0, "the goldens already disagree; the breaks below prove nothing"

    with monkeypatch.context() as m:
        m.setattr(d, "LABEL_GAP", 40.0)
        assert changed() > 0, "widening the collision gap changed nothing — the test is blind"

    original = d._axis_ticks
    with monkeypatch.context() as m:
        m.setattr(d, "_axis_ticks", lambda r, t: list(reversed(original(r, t))))
        assert changed() > 0, "reversing the tick priority changed nothing — order is not read"


# ── panel()'s default is unchanged, and its new band works ──────────────────────────────────

def test_PANELS_DEFAULT_RENDER_IS_UNCHANGED():
    """A145's rule: a new parameter may not move a byte for a caller that did not pass it.

    ⚠️ `panel()` MOVED DOWN THE FILE IN THIS ROUND — it must sit below `_LabelBands` and
    `TICK_NONE`, because Python resolves a default argument at `def` time. A move is exactly
    the kind of change that looks harmless and is not, so it is pinned rather than assumed.

    📊 THESE THREE CAUGHT A REAL REGRESSION IN THIS ROUND'S OWN FIRST DRAFT: the rewritten SVG
    line emitted `preserveAspectRatio` BEFORE `height` instead of after. Semantically identical,
    textually different, and it would have rewritten every existing panel render.
    """
    goldens = {
        "plain|120": "5e538cd623320d0c16b80347b406c361",
        "plain|240": "864ae9d5e0568f8eb86d315306afe6f1",
        "plain|420": "7d106bca550b38336dd0e875b2b81a04",
    }
    assert goldens, "no goldens (R-2254)"
    for key, digest in goldens.items():
        shape, width = key.split("|")
        actual = hashlib.md5(
            d.panel(_row(**SHAPES[shape]), label="W", width=int(width)).encode()).hexdigest()
        assert actual == digest, (
            f"panel()'s default render changed at width {width}. A new keyword argument may "
            f"not move a byte for a caller that did not pass it (A145's rule).")


def test_the_panel_draws_no_axis_until_it_is_asked():
    """`TICK_NONE` is the default and is what every pre-A235 render got."""
    assert _texts(d.panel(_row(), width=140)) == []


@pytest.mark.parametrize("ticks", [d.TICK_BOUNDS, d.TICK_PERCENTILES, d.TICK_EXTREMES])
def test_the_panel_draws_an_axis_when_it_is_asked(ticks):
    """🚨 MARC, v18: *"Might need more vertical real estate to include an x-axis with labels in
    the box-whisker diagram."* Before A235 no panel could draw one at any size."""
    svg = d.panel(_row(), width=140, height=56, ticks=ticks, head=False, stats=False)
    labels = _texts(svg)
    assert labels, f"{ticks} drew no axis labels at all"
    assert all(re.fullmatch(r"-?[\d.]+", t) for t in labels), \
        f"{ticks} emitted something that is not a number: {labels}"


def test_the_axis_band_is_the_only_thing_that_adds_height():
    """The band costs `LABEL_BAND` and nothing else, so a caller can budget a tile from the
    height it passed. 📊 `today._KPI_CHART_H = 56` is budgeted exactly this way."""
    plain = d.panel(_row(), width=140, height=56, head=False, stats=False)
    ticked = d.panel(_row(), width=140, height=56, ticks=d.TICK_EXTREMES,
                     head=False, stats=False)
    box = lambda svg: re.search(r"viewBox='0 0 \d+ (\d+)'", svg).group(1)   # noqa: E731
    assert int(ticked and box(ticked)) - int(box(plain)) == d.LABEL_BAND


def test_NO_AXIS_LABEL_IS_CLIPPED_BY_THE_VIEWBOX():
    """🚨 R-855's FAMILY, AND A RASTER IS WHAT FOUND IT. `place()` clamps to
    `[pad + half - 8, width - pad - half + 8]`: the ±8 lets a label hang outside the FRAME,
    which is right for `box()`, whose frame is inset from the viewBox by its own `pad`.

    📊 A PANEL'S HISTOGRAM STARTS AT x=0. With `pad=0` the same expression clamps a left-edge
    label to `half - 8`, which is OUTSIDE the viewBox. The Losing score tile, whose `min_value`
    is 0, rendered `)` where `0` belonged at 1440 — **and the DOM was perfect throughout**:
    the `<text>` element was present, correct, and half off the canvas.

    ⚠️ THE EXTREME CASE IS THE ONE THAT BREAKS, so the fixture puts min AND max hard on the
    bin bounds rather than comfortably inside them (R-843 — the pin must be able to move).
    """
    width = 140
    row = _row(min_value=0.0, max_value=80.0, p25=8.0, p75=72.0,
               whisker_lo=0.0, whisker_hi=80.0)
    svg = d.panel(row, width=width, height=56, ticks=d.TICK_EXTREMES, head=False, stats=False)
    placed = re.findall(r"<text x='([\d.]+)'[^>]*>([^<]*)</text>", svg)
    assert placed, "no labels were placed, so nothing is being checked (R-2254)"
    # ⚠️ TOLERANCE 0.1px, AND IT IS THE `:.1f` IN THE EMITTED ATTRIBUTE, NOT SLACK IN THE RULE.
    # With `pad=8` the clamp puts an extreme label's edge EXACTLY on the viewBox boundary, so a
    # coordinate rounded to one decimal can read 0.03px past it. The defect this test exists
    # for was 8px of overhang — two orders of magnitude clear of this.
    for x, text in placed:
        half = d._text_width(text) / 2.0
        assert float(x) - half >= -0.1, f"{text!r} at x={x} runs off the LEFT of the viewBox"
        assert float(x) + half <= width + 0.1, \
            f"{text!r} at x={x} runs off the RIGHT of the viewBox (width {width})"


def test_a_tick_outside_the_bins_is_skipped_rather_than_clamped():
    """🚨 A142's RULE, WHICH IS ABOUT TRUTH RATHER THAN LAYOUT: *clamping an outlier to the
    boundary tells the reader it is AT the extreme when it is BEYOND it.*

    📊 THIS IS LIVE, NOT HYPOTHETICAL. In 2026 week 3 `winning_points` publishes
    `max_value = 84` against `bin_max = 80`, so the MAX label is correctly absent from that
    tile and `above_max_count` is what tells the reader the tail is off the axis.
    """
    # `metric=` is what the page passes, and it is what makes these read `70` rather than
    # `70.0` — `fmt.precision_for` owns the decimals for a points metric (R-555).
    kw = dict(width=140, height=56, ticks=d.TICK_EXTREMES, head=False, stats=False,
              metric="winning_points")
    inside = d.panel(_row(max_value=70.0), **kw)
    beyond = d.panel(_row(max_value=84.0), **kw)
    assert "70" in _texts(inside), f"a value inside the bins was not labelled: {_texts(inside)}"
    assert "84" not in _texts(beyond), (
        f"a value beyond bin_max was drawn on the axis, which says the maximum is somewhere "
        f"it is not: {_texts(beyond)}")


def test_the_head_and_the_stats_can_be_suppressed_independently():
    """🚨 THE STATS FLAG WAS INERT IN THIS ROUND'S FIRST DRAFT and the failure was silence.
    The body built its table into a local also called `stats`, so `if stats` read the LIST —
    always truthy — and `stats=False` printed the table it had asked not to. A shadowed
    parameter fails by doing nothing."""
    row = _row()
    assert "cfdb-dist-head" in d.panel(row, label="W", width=140)
    assert "cfdb-dist-stats" in d.panel(row, label="W", width=140)
    assert "cfdb-dist-head" not in d.panel(row, label="W", width=140, head=False)
    assert "cfdb-dist-stats" not in d.panel(row, label="W", width=140, stats=False)
    bare = d.panel(row, label="W", width=140, head=False, stats=False)
    assert "cfdb-dist-head" not in bare and "cfdb-dist-stats" not in bare


def test_the_panel_prints_no_median_beside_the_chart():
    """> **MARC, 2026-09-25:** *"Another thing that helps the histograms is not presenting the
    median next to the histogram. Median provides the information below."*

    ⚠️ THIS IS WHY THE KPI ROW MOVED OFF `thumbnail()`, AND IT IS PINNED ON BOTH SIDES —
    `thumbnail` really does print one, so a test asserting only the panel's silence could pass
    against a renderer that had stopped drawing anything at all.
    """
    row = _row()
    assert "cfdb-dist-median" in d.thumbnail(row, width=72), \
        "thumbnail stopped printing a median, so this test no longer proves a difference"
    assert "cfdb-dist-median" not in d.panel(row, width=140, height=56, head=False, stats=False)
    # the median is still DRAWN, as the bold rule Marc kept — just without a number beside it
    assert "stroke-opacity='0.95'" in d.panel(row, width=140, height=56,
                                              head=False, stats=False), \
        "the median rule is gone from the chart as well as the number"


def test_a_text_bearing_svg_never_stretches():
    """🚨 `preserveAspectRatio='none'` SCALES TEXT NON-UNIFORMLY. An unlabelled panel may
    stretch to fill its container — that is every pre-A235 render and the bars simply get wider
    — but the moment there is a digit in the SVG, a stretched box renders it squashed or
    splayed by whatever ratio the container happened to have. **Invisible in the DOM.**"""
    plain = d.panel(_row(), width=140, height=56, head=False, stats=False)
    ticked = d.panel(_row(), width=140, height=56, ticks=d.TICK_EXTREMES,
                     head=False, stats=False)
    assert "preserveAspectRatio='none'" in plain and not _texts(plain)
    assert "preserveAspectRatio='none'" not in ticked and _texts(ticked)
    assert "max-width:100%" in ticked, "a fixed-width chart must still not overflow its tile"
