"""命令行入口测试；所有输出只写 var/。"""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAR = os.path.join(ROOT, "var")
GRIDS = os.path.join(ROOT, "samples", "grids")
EXPECTED = os.path.join(ROOT, "samples", "expected")


def run_cli(*extra, env=None):
    cmd = [sys.executable, "-m", "isodraw", "extract"] + list(extra)
    return subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True, env=env,
    )


class CliTest(unittest.TestCase):
    def test_extract_writes_and_prints_stat(self):
        out = os.path.join(VAR, "cli_hill")
        proc = run_cli("--grid", os.path.join(GRIDS, "hill.txt"), "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "STAT|lines=2|max_segments=12\n")
        with open(os.path.join(out, "lines.txt"), encoding="utf-8") as fh:
            actual = fh.read()
        with open(os.path.join(EXPECTED, "hill.txt"), encoding="utf-8") as fh:
            expected = fh.read()
        self.assertEqual(actual, expected)
        self.assertTrue(os.path.exists(os.path.join(out, "index.html")))

    def test_deterministic_across_hash_seeds(self):
        outs = []
        for seed in ("0", "1", "987654"):
            out = os.path.join(VAR, f"cli_det_{seed}")
            env = dict(os.environ, PYTHONHASHSEED=seed)
            proc = run_cli("--grid", os.path.join(GRIDS, "saddle.txt"),
                           "--out", out, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(os.path.join(out, "lines.txt"), encoding="utf-8") as fh:
                outs.append((fh.read(), proc.stdout))
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[1], outs[2])

    def test_bad_grid_exits_nonzero_and_writes_nothing(self):
        bad = os.path.join(VAR, "bad_grid.txt")
        out = os.path.join(VAR, "cli_bad_out")
        os.makedirs(out, exist_ok=True)
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("ncols 3\nnrows 3\nx0 0\ny0 0\ndx 1\ndy 1\nlevels 1.0\n")
            fh.write("0 0 0\n0 1 0\n")  # 少一行数据
        proc = run_cli("--grid", bad, "--out", out)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(out, "lines.txt")))
        self.assertFalse(os.path.exists(os.path.join(out, "index.html")))

    def test_missing_file_exits_nonzero(self):
        out = os.path.join(VAR, "cli_missing_out")
        proc = run_cli("--grid", os.path.join(VAR, "nope.txt"), "--out", out)
        self.assertNotEqual(proc.returncode, 0)

    def test_negative_dx_rejected(self):
        bad = os.path.join(VAR, "bad_dx.txt")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("ncols 2\nnrows 2\nx0 0\ny0 0\ndx -1\ndy 1\nlevels 1\n")
            fh.write("0 0\n0 2\n")
        out = os.path.join(VAR, "cli_bad_dx_out")
        self.assertNotEqual(run_cli("--grid", bad, "--out", out).returncode, 0)


if __name__ == "__main__":
    unittest.main()
