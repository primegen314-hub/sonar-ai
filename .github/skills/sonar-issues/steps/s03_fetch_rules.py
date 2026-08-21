"""Step 03 - Fetch full rule descriptions (why is this an issue / how to fix)
for every distinct rule in the fetched issues -> _raw/rules.json.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import init_console
from lib import config


def main():
    init_console()
    args = config.build_parser(__doc__).parse_args()
    settings = config.Settings(args)
    settings.load_meta()

    issues_data = config.load_json(os.path.join(settings.raw_dir, "issues.json"))
    rule_keys = sorted({issue["rule"] for issue in issues_data.get("issues", []) if issue.get("rule")})
    print(f"[s03] {len(rule_keys)} distinct rules to fetch")

    client = settings.sonar_client()
    rules = {}
    for key in rule_keys:
        rules[key] = client.rule_show(key)
        print(f"[s03]   {key}: {rules[key].get('name', '?')}")

    config.dump_json(os.path.join(settings.raw_dir, "rules.json"), rules)
    print(f"[s03] wrote {settings.raw_dir}\\rules.json")


if __name__ == "__main__":
    main()
