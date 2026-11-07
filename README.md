# SYE6601-warehouse
A place where put our group project product.

## Modules

| Module | Purpose | Status |
| --- | --- | --- |
| [07A Confidence A](modules/confidence_a_mvp/README.md) | Evidence scorecards and offline metrics. 0.2 adds graph-building risk levels on top of the 0.1 obligation score | 0.1 snapshots still score; 0.2 levels and business rules remain provisional |

### Run the 07A module

Requires Python 3.10 or newer. Runtime and tests use the Python standard library.

```sh
cd modules/confidence_a_mvp
python tools/run_demo.py
```

The command runs the tests and writes demo outputs under the module's `outputs/` directory.
The fixtures are synthetic integration examples, not experimental results.
0.2 cases cover a missing required baseline check, an unexpanded clause, critical 403 and pagination gaps, a sufficiently evidenced refusal, a non-critical pruned reservation, and the DYN-01 ticket dependency before and after it is fetched.
The level describes evidence and process quality inside the declared scope. It is not a graph-completeness score and not an answer probability.

The [interface draft](modules/confidence_a_mvp/docs/01_接口草案.md) and
[pending team decisions](modules/confidence_a_mvp/docs/03_待团队确认.md) describe what needs to be agreed before integration.
