import xml.etree.ElementTree as ET

import os
import requests
import subprocess

os.chdir(os.path.dirname(__file__))

subprocess.run([
    "docker", "run", "-d",
        "--name=selenium-chrome",
        "--restart=unless-stopped",
        "--shm-size=2g",
        "-e", "START_XVFB=false",
        "-e", "SE_NODE_MAX_SESSIONS=8",
        "-e", "SE_NODE_OVERRIDE_MAX_SESSIONS=true",
        "selenium/standalone-chrome:4.0.0-rc-1-prerelease-20210713"
])
selenium_ip = subprocess.check_output([
    "docker", "inspect", 
        "--format", "{{ .NetworkSettings.IPAddress }}", 
        "selenium-chrome"
], encoding='utf-8').strip()

def run_tests(wagtail_version):
    b = subprocess.run([
        "docker", "build", "-q",
            "-f", "Dockerfile", 
            "--build-arg", "WAGTAIL_VERSION", 
            "..",
    ], capture_output=True, env={'WAGTAIL_VERSION': wagtail_version})
    
    if b.returncode!=0:
        raise "erk"

    image = b.stdout.decode('ascii').strip()

    r = subprocess.run([
        "docker", "run",# "-it",
            "--rm",
            "-e", "SELENIUM_HOST=" + selenium_ip,
            image,
    ], capture_output=False)

    #print(r.returncode, r.returncode, r.stdout, r.stderr)
    #print(r.stdout.decode('ascii'))







root = ET.fromstring(requests.get("https://pypi.org/rss/project/wagtail/releases.xml").text)

for el in list(root.findall('.//item/title'))[:10]:
    version = el.text

    print("Testing version", version)
    run_tests(version)
