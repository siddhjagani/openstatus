#!/usr/bin/perl
# libsql health = "can it answer a query?", not "is the port open?".
# On 2026-10-01 sqld jammed for ~12h (every connection: "Timed out while opening
# database connection" / 429 DbCreateTimeout) while the old port-only check kept
# reporting healthy. This runs SELECT 1 over the HTTP API with a hard 4s budget.
use strict;
use warnings;
use IO::Socket::INET;

$SIG{ALRM} = sub { exit 1 };
alarm 4;
my $s = IO::Socket::INET->new(PeerAddr => "127.0.0.1:8080", Timeout => 3) or exit 1;
my $body = q({"statements":["SELECT 1"]});
print $s "POST / HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\n"
  . "Content-Length: " . length($body) . "\r\n\r\n$body";
my $res = join("", <$s>);
exit(($res =~ m{^HTTP/1\.[01] 200} && $res =~ /"rows"/) ? 0 : 1);
