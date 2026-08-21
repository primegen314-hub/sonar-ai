"""Step 01 - Validate .env, reach SonarQube, and mint+persist a user token if needed.

The LDAP user/password from .env is used exactly once: to call
api/user_tokens/generate. The resulting SONAR_TOKEN is written back to .env
and used for every later request.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import init_console, fail
from lib import config, envfile
from lib.sonar_api import SonarError


def main():
    init_console()
    args = config.build_parser(__doc__).parse_args()
    settings = config.Settings(args)

    if settings.fixtures:
        print("[s01] fixtures mode - skipping authentication")
        return

    if not settings.host:
        fail("No Sonar host. Paste a Sonar URL or set SONAR_HOST in .env")

    client = settings.sonar_client()
    print(f"[s01] Sonar host : {settings.host}")

    if settings.token:
        try:
            print(f"[s01] token OK (server version {client.version()})")
            # a password may still be sitting in .env from an earlier run - clear it,
            # the token is all we need from now on
            if settings.password and settings.env_path:
                envfile.update_env(settings.env_path, "SONAR_PASSWORD", "")
                print("[s01] SONAR_PASSWORD cleared from .env - the token replaces it")
            return
        except SonarError as e:
            print(f"[s01] existing SONAR_TOKEN failed ({e}); will try to mint a new one")
            settings.token = None
            client.token = None

    if not settings.user:
        fail("No SONAR_USER in .env")

    password_from_env = bool(settings.password)
    password = settings.password
    if not password:
        if sys.stdin.isatty():
            import getpass
            password = getpass.getpass(f"[s01] Sonar LDAP password for {settings.user} (not stored): ")
        else:
            fail("No SONAR_PASSWORD in .env and no interactive terminal to prompt. "
                 "Either set it temporarily in .env or run this step from a terminal.")
    if not password:
        fail("Empty password")
    client.password = password

    print(f"[s01] server version {client.version()}")
    token_name = f"sonar-issues-{settings.user}-{int(time.time())}"
    print(f"[s01] generating user token '{token_name}' ...")
    token = client.generate_token(token_name)

    env_path = settings.env_path or envfile.env_path(settings.skill_dir)
    envfile.update_env(env_path, "SONAR_TOKEN", token)
    print(f"[s01] SONAR_TOKEN written to {env_path}")
    if password_from_env:
        envfile.update_env(env_path, "SONAR_PASSWORD", "")
        print("[s01] SONAR_PASSWORD cleared from .env - the token replaces it from now on")
    print("[s01] done - later steps authenticate with the token, not your password")


if __name__ == "__main__":
    main()
