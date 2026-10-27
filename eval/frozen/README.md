# Frozen test matches

Recorded matches kept only for tests. Nothing regenerates them, and the site does not load them.

- `m-seed-29-before-ax44.json`: `eval/fixtures/demo-1021.json` as it was before Ax44 (#245), when
  the simulator still put players on their usual spots at set pieces. Harbour City 3-1 Northgate Rovers,
  turning points at 37', 66' and 79'. Tests that check how the momentum detector, the Judge prompt
  and the What-if chips behave on one specific match read this file, so a later simulator change does
  not change what they check.

The match the site opens and the tests that check the simulator's own output use
`eval/fixtures/demo-1021.json`, which `uv run scripts/make_demo.py --seed 29` regenerates.
