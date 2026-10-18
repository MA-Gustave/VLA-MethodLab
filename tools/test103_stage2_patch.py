#!/usr/bin/env python3
"""Version-pinned, local compile overlay: mutate only a copy of Stage 2 header."""
from pathlib import Path
import hashlib

# Fixed exact source anchor. Abort on an unexpected upstream change.
ANCHOR="""        dst[bs_dist] = escape_result;
        src += bs_dist + 2;
        dst += bs_dist + 1;
"""
EXPECTED_SOURCE_SHA256 = 'd8f52d5cc086d7ec493a9a9c8c1d670afda4e362a68e8a8277f7c3d576af319e'
OPT=r"""
#if defined(SIMDJSON_TEST103_SIMPLE_RUN)
        // Test 103: adjacent simple JSON escapes. Every pair is handled only
        // when its second char has a nonzero mapping; never consume Unicode.
        // This is run on the padded parse path; scratch fallback remains padded.
#if defined(SIMDJSON_TEST103_NL4)
        // Four consecutive literal backslash+'n' pairs -> four newlines.
        // Short-circuit checks ensure a quote/non-backslash breaks the run.
        while (src[0] == '\\' && src[1] == 'n' &&
               src[2] == '\\' && src[3] == 'n' &&
               src[4] == '\\' && src[5] == 'n' &&
               src[6] == '\\' && src[7] == 'n') {
          dst[0] = '\n'; dst[1] = '\n'; dst[2] = '\n'; dst[3] = '\n';
          dst += 4; src += 8;
        }
#endif
        while (src[0] == '\\') {
          // escape_map[u] == 0; null/invalid sequences are left for the
          // original validated path. Do not consume the terminating quote.
          const uint8_t decoded = escape_map[src[1]];
          if (decoded == 0) { break; }
          *dst++ = decoded;
          src += 2;
        }
#endif
"""

def create_overlay(source, destination):
    source=Path(source);destination=Path(destination)
    text=source.read_text()
    if hashlib.sha256(source.read_bytes()).hexdigest()!=EXPECTED_SOURCE_SHA256:
        raise RuntimeError('Stage 2 source SHA256 mismatch; refusing unverified overlay')
    if text.count(ANCHOR)!=3:
        # three occurrences: parse_string, parse_string_safe, parse_wobbly_string
        raise RuntimeError('Unsupported Stage 2 source layout, cannot safely patch')
    left,right=text.split(ANCHOR,1)
    patched=left+ANCHOR+OPT+right
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(patched)
    return {'source_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'patched_sha256':hashlib.sha256(patched.encode()).hexdigest()}
