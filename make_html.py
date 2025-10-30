import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
TEMPLATE_PATH = BASE / "test.html.template"
OUT_PATH = BASE / "test.html"

def main():
  try:
    cfg = json.loads(CONFIG_PATH.read_text())
  except Exception as e:
    print(f"Failed to read/parse {CONFIG_PATH}: {e}", file=sys.stderr)
    return 1

  if "i_size" not in cfg or "t_sizes" not in cfg or "prefix" not in cfg:
    print("config.json must contain 'i_size' and 't_sizes' and 'prefix' keys", file=sys.stderr)
    return 2

  f_prefix = cfg["prefix"]
  i_size = cfg["i_size"]
  t_sizes = cfg["t_sizes"]

  try:
    print("reading {}".format(TEMPLATE_PATH))
    template = TEMPLATE_PATH.read_text()
  except Exception as e:
    print(f"Failed to read template {TEMPLATE_PATH}: {e}", file=sys.stderr)
    return 3

  # Replace placeholders. Use json.dumps for t_sizes so it becomes a valid JS array (including brackets).
  out_html = template.replace("I_SIZE", json.dumps(i_size)).replace("T_SIZES", json.dumps(t_sizes)).replace("S_PREFIX", json.dumps(f_prefix))

  try:
    print("writing {}".format(OUT_PATH))
    OUT_PATH.write_text(out_html)
  except Exception as e:
    print(f"Failed to write output {OUT_PATH}: {e}", file=sys.stderr)
    return 4

  return 0

if __name__ == "__main__":
  raise SystemExit(main())
