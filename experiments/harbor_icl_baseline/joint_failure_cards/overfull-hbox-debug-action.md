# Harness-TrajecDebug Debug-Action Card: overfull-hbox

## Source Signal

This card is synthesized from a failed Codex + GPT-5.5 trajectory and the
official verifier footprint. It is not a teacher-success replay.

The failed run did useful work:

- it kept `main.tex` and `synonyms.txt` unchanged;
- it compiled successfully;
- it removed all `Overfull \hbox` warnings.

But the official verifier still failed `test_input_file_matches`:

```text
AssertionError: modified input.tex must only modify words in synonyms.txt
assert ('unknown' == 'new' ... and 'new' in {'anonymous', 'mysterious',
'strange', 'unfamiliar', 'unidentified', 'unknown'})
```

The root cause was not LaTeX compilation. The root cause was a wrong
commitment: after seeing the overfull warnings disappear, the agent trusted
semantic paraphrases and did not run the verifier's token-level synonym-family
check.

## Critical Step

The decisive repair is:

> Make every changed token a member of the original token's exact
> `synonyms.txt` family, then verify that constraint before trusting the clean
> LaTeX log.

The key negative example is `unknown -> new`. It looks semantically plausible,
but it is illegal because `new` is in the `young` family, not the `unknown`
family.

## Action Boundary

Build the solution around a constrained substitution table, not a free rewrite.
Use only legal synonym-family replacements such as:

```text
curious -> inquisitive
riotous -> wild
responsiveness -> awareness
creative -> imaginative
weatherbeaten -> worn
pathfinder -> pioneer
```

These replacements are enough to remove the overfull boxes while preserving the
verifier's token contract. Avoid broad substitutions like `unknown -> new`,
`dreams -> hopes`, or any phrase-level paraphrase unless the exact old and new
word cores appear in the same line of `synonyms.txt`.

## Minimal Coding Plan

In `/app`, run a small deterministic edit:

```bash
cp /app/input.tex /tmp/original_input.tex

perl -0pi -e 's/\bcurious\b/inquisitive/g; s/\briotous\b/wild/g; s/\bresponsiveness\b/awareness/g; s/\bcreative\b/imaginative/g; s/\bweatherbeaten\b/worn/g; s/\bpathfinder\b/pioneer/g' /app/input.tex

pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

## Self-Check

After editing, run both gates:

```bash
perl -we '
use strict; use warnings;
sub slurp { my ($p)=@_; open my $fh, "<", $p or die $!; local $/; <$fh> }
my $orig = slurp("/tmp/original_input.tex");
my $agent = slurp("/app/input.tex");
my $syn = slurp("/app/synonyms.txt");
my %synonyms;
for my $line (split /\n/, $syn) {
  my @words = split /, /, $line;
  my %family = map { $_ => 1 } @words;
  $synonyms{$_} = \%family for @words;
}
$orig =~ s/---/ --- /g; $agent =~ s/---/ --- /g;
my @o = $orig =~ /\S+/g; my @a = $agent =~ /\S+/g;
die "token count mismatch" unless @o == @a;
for my $i (0..$#o) {
  my ($op,$ow,$os) = $o[$i] =~ /^(\W*)(.*?)(\W*)$/;
  my ($ap,$aw,$as) = $a[$i] =~ /^(\W*)(.*?)(\W*)$/;
  die "punctuation changed: $o[$i] -> $a[$i]" unless $op eq $ap && $os eq $as;
  die "illegal synonym: $ow -> $aw" unless $ow eq $aw || (exists $synonyms{$ow} && exists $synonyms{$ow}{$aw});
}
my $log = slurp("/app/main.log");
die "compile marker missing" unless $log =~ /Output written on main\.pdf/;
die "overfull found" if $log =~ /Overfull \\hbox/;
print "synonym legality and overfull gates pass\n";
'
```

If this self-check passes, the historical Codex failure has been repaired: the
artifact is no longer just typographically clean; it is also legal under the
token-pair synonym verifier.
