# Spring terminal cleanup review

Selected reloads remain ink1100/color700. Painting prefixes are preserved byte-for-byte except removal of their final M2; cleanup is appended after the previous final park, then the machine parks again and terminates with M2.
Terminal routine: three water visits, each10s dwell/three agitation cycles with existing shallow wipe/lip; sponge twice4s, then Z35/park/M2. No final rewet or pigment load. Contact XYZ/feed/depth are unchanged; intermediate color-change routines are unchanged.
Standalone END_CLEANUP_INK_FROM_PARK / COLOR_FROM_PARK files require the PREVIOUS job to have completed at G54 X800 Y800 Z35, with registration preserved. Do not run concurrently, from post-home, or from an interrupted/unknown position. Full files independently start0/900/35.
AIR includes noncontact terminal XY at35. No hardware was operated. Cleanliness is not certified; existing execution gates remain.
