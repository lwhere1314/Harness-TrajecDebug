#!/bin/bash
set -u

write_reward() {
  mkdir -p /logs/verifier
  echo "$1" > /logs/verifier/reward.txt
}

fail() {
  echo "FAIL: $*"
  write_reward 0
  exit 1
}

if [ "$PWD" = "/" ]; then
  fail "No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
fi

cmp -s /tests/main.tex /app/main.tex || fail "main.tex must not be modified"
cmp -s /tests/synonyms.txt /app/synonyms.txt || fail "synonyms.txt must not be modified"

cp /tests/main.tex /app/main_original.tex || fail "could not copy verifier main.tex"
if ! /usr/bin/pdflatex -jobname=main main_original.tex >/logs/verifier/pdflatex.txt 2>&1; then
  cat /logs/verifier/pdflatex.txt
  fail "Solution must compile successfully"
fi

if ! grep -q "Output written on main.pdf" /app/main.log; then
  fail "Solution must compile successfully"
fi

if grep -q "Overfull \\\\hbox" /app/main.log; then
  fail "Solution must remove all overfull hboxes"
fi

if ! perl -we '
use strict;
use warnings;

sub slurp {
    my ($path) = @_;
    open my $fh, "<", $path or die "cannot open $path: $!";
    local $/;
    return <$fh>;
}

my $text = slurp("/tests/input.tex");
my $text_agent = slurp("/app/input.tex");
my $syn_text = slurp("/tests/synonyms.txt");

my %synonyms;
for my $line (split /\n/, $syn_text) {
    next unless length $line;
    my @words = split /, /, $line;
    my %family = map { $_ => 1 } @words;
    for my $word (@words) {
        $synonyms{$word} = \%family;
    }
}

$text =~ s/---/ --- /g;
$text_agent =~ s/---/ --- /g;
my @tokens = $text =~ /\S+/g;
my @tokens_agent = $text_agent =~ /\S+/g;
die "modified input.tex must only modify words in synonyms.txt\n"
    unless @tokens == @tokens_agent;

for my $i (0 .. $#tokens) {
    my $token = $tokens[$i];
    my $token_agent = $tokens_agent[$i];
    my ($p, $w, $s) = $token =~ /^(\W*)(.*?)(\W*)$/;
    my ($p_agent, $w_agent, $s_agent) =
        $token_agent =~ /^(\W*)(.*?)(\W*)$/;
    die "modified input.tex must only modify words in synonyms.txt\n"
        unless defined $w_agent;
    die "modified input.tex must only modify words in synonyms.txt\n"
        unless $p eq $p_agent && $s eq $s_agent;
    die "modified input.tex must only modify words in synonyms.txt\n"
        unless $w eq $w_agent
            || (exists $synonyms{$w} && exists $synonyms{$w}{$w_agent});
}
print "all verifier gates passed\n";
'; then
  fail "modified input.tex must only modify words in synonyms.txt"
fi

write_reward 1
echo "PASS: all verifier gates passed"
