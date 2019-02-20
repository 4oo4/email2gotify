import argparse
import base64
import email
import json
import re
from subprocess import Popen, PIPE, STDOUT
import sys

CURL_PROGRAM = 'curl'
PUSH_TYPE = 'note'

TRACE_FILE = 'curl.trace'
DEFAULT_ENCODING = 'utf-8'

parser = argparse.ArgumentParser(description='Send Gotify PUSH based on email message')
parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin,
    help='MIME-encoded email file(if empty, stdin will be used)')
parser.add_argument('--key', help='API key for Gotify', required=True)
parser.add_argument('--url', help='The URL of your Gotify instance (e.g. https://gotify.example.com)', required=True)
parser.add_argument('--debug', help='Enable debug mode', action='store_true')
args = parser.parse_args()
debug_mode = args.debug
if debug_mode:
    print 'Debug mode enabled'

msg = email.message_from_file(args.infile)
args.infile.close()

def decode_field(field_raw):
    match = re.match(r'\=\?([^\?]+)\?([BQ])\?([^\?]+)\?\=', field_raw)
    if match:
        charset, encoding, field_coded = match.groups()
        if encoding == 'B':
            field_coded = base64.decodestring(field_coded)
        return field_coded.decode(charset)
    else: 
        return field_raw

subject_raw = msg.get('Subject', '')
subject = decode_field(subject_raw)

sender = decode_field(msg.get('From', ''))

body_text = ''
for part in msg.walk():
    if part.get_content_type() == 'text/plain':
        body_part = part.get_payload()
        if part.get('Content-Transfer-Encoding') == 'base64':
            body_part = base64.decodestring(body_part)
        part_encoding = part.get_content_charset()
        if part_encoding:
            body_part = body_part.decode(part_encoding)
        else:
            body_part = body_part.decode()

        if body_text:
            body_text = '%s\n%s' % (body_text, body_part)
        else:
            body_text = body_part

body_text = '%s\nFrom: %s' % (body_text, sender)

push_headers = {
    'title': subject,
    'message': body_text,
    'priority': 5,
}

program = CURL_PROGRAM
cmdline = [program, args.url + "/message?token=" + args.key, '-s', '-X', 'POST']
header_pairs = [['-d', '%s=%s' % (header, data)] for header, data in push_headers.iteritems()]
cmdline += [item.encode(DEFAULT_ENCODING) for sublist in header_pairs for item in sublist]
if debug_mode:
    cmdline += ['--trace-ascii', TRACE_FILE]
    print 'Command line:'
    print '----------'
    print ' '.join(cmdline)
    print '----------'

process = Popen(cmdline, stdout=PIPE, stderr=STDOUT)
stdout, stdin = process.communicate()
exit_code = process.returncode
if exit_code:
    print '%s returned exit code %d' % (program, exit_code)
    print 'Output:'
    print '---------'
    print stdout
    print '---------'
    sys.exit(exit_code)
else:
    try:
        server_response = json.loads(stdout)
    except:
        if debug_mode:
            print 'Server response was not JSON:'
            print '--------------'
            print stdout
            print '--------------'
        raise
    error = server_response.get('error')
    if error:
        print 'Server returned error:'
        print error.get('message')
        sys.exit(1)
