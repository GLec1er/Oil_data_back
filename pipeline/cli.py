"""Command line entry point: publish, wait, verify, replay."""
import argparse
import sys
from datetime import datetime, timezone

from pipeline import config, scenario
from pipeline.generator import SCENARIOS, generate
from pipeline.snapshot import replay
from pipeline.verify import bronze_count, fingerprint, observe, run


def _publish(args) -> int:
    from pipeline.publisher import publish

    if args.phase == "baseline":
        messages = scenario.baseline()
    elif args.phase == "outage":
        messages = scenario.outage()
    else:
        start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
        messages = generate(
            args.seed, args.wells.split(","), start, args.count, args.scenario
        )
    print(f"published {publish(messages)} messages to {config.TOPIC}")
    return 0


def _wait(args) -> int:
    from pipeline.publisher import wait_until

    def ready() -> bool:
        seen = observe(config.BRONZE_DIR, config.MARTS_DIR)
        return seen["bronze"] >= args.bronze and seen["silver"] >= args.silver

    ok = wait_until(ready, args.timeout)
    print("ready" if ok else "timed out waiting for the pipeline")
    return 0 if ok else 1


def _verify(args) -> int:
    code = run(config.BRONZE_DIR, config.MARTS_DIR, args.stage)
    current = fingerprint(config.MARTS_DIR)
    if args.fingerprint_out:
        open(args.fingerprint_out, "w").write(current)
    if args.fingerprint_in:
        same = open(args.fingerprint_in).read() == current
        print("  " + ("OK   content unchanged" if same else "FAIL content changed"))
        code = code or (0 if same else 1)
    return code


def _replay(_args) -> int:
    manifest = replay(config.BRONZE_DIR, config.MARTS_DIR)
    print(f"replayed from Bronze ({bronze_count(config.BRONZE_DIR)} records):")
    print(f"  snapshot {manifest['snapshot_id']} counts {manifest['counts']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    pub = sub.add_parser("publish")
    pub.add_argument("--phase", choices=["baseline", "outage", "generate"], default="generate")
    pub.add_argument("--seed", type=int, default=1)
    pub.add_argument("--wells", default="NORTH-07,EAST-12")
    pub.add_argument("--start", default=datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z"))
    pub.add_argument("--count", type=int, default=8)
    pub.add_argument("--scenario", choices=SCENARIOS, default="normal")
    pub.set_defaults(func=_publish)

    wait = sub.add_parser("wait")
    wait.add_argument("--bronze", type=int, required=True)
    wait.add_argument("--silver", type=int, required=True)
    wait.add_argument("--timeout", type=float, default=180)
    wait.set_defaults(func=_wait)

    ver = sub.add_parser("verify")
    ver.add_argument("--stage", choices=sorted(scenario.EXPECTED), default="final")
    ver.add_argument("--fingerprint-out")
    ver.add_argument("--fingerprint-in")
    ver.set_defaults(func=_verify)

    rep = sub.add_parser("replay")
    rep.set_defaults(func=_replay)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
