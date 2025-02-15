#!/usr/bin/env python
import xml.etree.ElementTree as ET

import os
import requests
import subprocess
import sys

os.chdir(os.path.dirname(__file__))

subprocess.run([
    "docker", "run", "-d",
        "--name=selenium-chrome-4.10.0",
        "--restart=unless-stopped",
        "--shm-size=2g",
        "-e", "START_XVFB=false",
        "-e", "SE_NODE_MAX_SESSIONS=8",
        "-e", "SE_NODE_OVERRIDE_MAX_SESSIONS=true",
        "selenium/standalone-chrome:4.10.0"
])
selenium_ip = subprocess.check_output([
    "docker", "inspect", 
        "--format", "{{ .NetworkSettings.IPAddress }}", 
        "selenium-chrome-4.10.0"
], encoding='utf-8').strip()
assert selenium_ip, "Selenium container not found!"

def run_tests(wagtail_version):
    b = subprocess.run([
        "docker", "build", "-q",
            "-f", "Dockerfile", 
            "--build-arg", "WAGTAIL_VERSION", 
            "..",
    ], capture_output=True, env={'WAGTAIL_VERSION': wagtail_version})
    
    assert b.returncode==0, "Unable to build container: " + b.stderr.decode('ascii', errors="ignore").strip()

    image = b.stdout.decode('ascii').strip()

    r = subprocess.run([
        "docker", "run",# "-it",
            "--rm",
            "-e", "SELENIUM_HOST=" + selenium_ip,
            image,
    ], capture_output=False)
    return r.returncode

def skip_old_rcs(versions):
    ret, released = [], {}
    for version in versions:
        bits = version.split(".")
        if "rc" in version and (bits[0],) in released:
            continue
        if (bits[0], bits[1]) in released:
            continue
        released[(bits[0],)] = True
        released[(bits[0], bits[1])] = True
        ret.append(version)
    return ret


root = ET.fromstring(requests.get("https://pypi.org/rss/project/wagtail/releases.xml").text)
versions = [el.text for el in root.findall('.//item/title')]
versions = skip_old_rcs(versions)

number_to_test = int(sys.argv[1]) if len(sys.argv)>1 else 10
results = []

for version in versions[:number_to_test]:
    print("Testing version", version)
    results.append((version, run_tests(version)))

def parse_version(version):
    bits = version.replace("rc", ".0.").split(".") + ["0"]*3
    return tuple(int(i) for i in bits[:4])

results.sort(key=lambda i: parse_version(i[0]), reverse=True)

readme = open("../README.md", "r").read()
COMPAT_MATRIX_HEADER = 'Wagtail version | Passing tests?\n----------------|---------------\n'
assert COMPAT_MATRIX_HEADER in readme
header, footer = readme.split(COMPAT_MATRIX_HEADER, 1)
footer = "\n##" + footer.split("##", 1)[1]

table = "".join('{:15} | {:}\n'.format(ver, ':heavy_check_mark:' if r==0 else ':x:') for ver, r in results)

with open("../README.md", "w") as f:
    f.write(header + COMPAT_MATRIX_HEADER + table + footer)
