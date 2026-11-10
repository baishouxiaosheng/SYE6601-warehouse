# SYE6601-warehouse
A place where put our group project product.

## Modules

The November dynamic evidence prototype has a [local demo and integration guide](docs/dynamic-evidence/README.md).
Run `python -m dynamic_evidence --case DYN-01` from the repository root to replay the workflow with fixture models.

| Module | Purpose | Status |
| --- | --- | --- |
| [07A Confidence A MVP](modules/confidence_a_mvp/README.md) | Explainable evidence scorecards and per-run evaluation metrics | Standalone MVP; interface and business assumptions pending team confirmation |

### Run the 07A module

Requires Python 3.10 or newer. Runtime and tests use the Python standard library.

```sh
cd modules/confidence_a_mvp
python tools/run_demo.py
```

The command runs the tests and writes demo outputs under the module's `outputs/` directory.
The fixtures are synthetic integration examples, not experimental results.

The [interface draft](modules/confidence_a_mvp/docs/01_接口草案.md) and
[pending team decisions](modules/confidence_a_mvp/docs/03_待团队确认.md) describe what needs to be agreed before integration.
