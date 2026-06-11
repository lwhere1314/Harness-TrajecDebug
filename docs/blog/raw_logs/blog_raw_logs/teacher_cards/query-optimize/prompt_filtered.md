# Prompt-Filtered Teacher Snippets: query-optimize

This card is a generic filtered teacher-log baseline. It keeps useful
snippets from a previous passing run but does not expose the structured
process-diagnosis schema used by the main method.

## Outcome
Task: query-optimize
Teacher outcome: reward=1.0
Verifier summary: tests=6, passed=6, failed=0

## Captured artifact snippets
Artifact: /app/sol.sql
```sql
WITH
sense_synsets AS MATERIALIZED (
  SELECT
    s.wordid,
    s.synsetid,
    syn.domainid,
    syn.posid,
    COUNT(*) AS sense_count
  FROM senses s
  JOIN synsets syn ON syn.rowid = s.synsetid
  GROUP BY s.wordid, s.synsetid
),
word_stats AS (
  SELECT
    ss.wordid,
    COUNT(*) AS total_synsets,
    SUM(ss.sense_count) AS total_senses,
    COUNT(DISTINCT ss.domainid) AS distinct_domains,
    COUNT(DISTINCT ss.posid) AS distinct_posids
  FROM sense_synsets ss
  GROUP BY ss.wordid
  HAVING COUNT(*) >= 2
    AND COUNT(DISTINCT ss.domainid) >= 2
    AND SUM(ss.sense_count) >= 2
),
ranked_words AS MATERIALIZED (
  SELECT
    ws.wordid AS word_id,
    ws.total_synsets,
    ws.total_senses,
    ws.distinct_domains,
    ws.distinct_posids
  FROM word_stats ws
  ORDER BY
    ws.total_senses DESC,
    ws.total_synsets DESC,
    ws.distinct_domains DESC,
    word_id ASC
  LIMIT 500
),
top_synsets AS MATERIALIZED (
  SELECT
    ss.wordid,
    MIN((1000000 - ss.sense_count) * 1000000 + ss.synsetid) AS top_key
  FROM sense_synsets ss
  JOIN ranked_words rw ON rw.word_id = ss.wordid
  GROUP BY ss.wordid
)
SELECT
  rw.word_id,
  w.word AS word,
  rw.total_synsets,
  rw.total_senses,
  rw.distinct_domains,
  rw.distinct_posids,
  ts.top_key % 1000000 AS top_synsetid,
  1000000 - ts.top_key / 1000000 AS top_synset_sense_count
FROM ranked_words rw
JOIN words w ON w.rowid = rw.word_id
JOIN top_synsets ts ON ts.wordid = rw.word_id
ORDER BY
  rw.total_senses DESC,
  rw.total_synsets DESC,
  rw.distinct_domains DESC,
  rw.word_id ASC;
```

## Filtered log snippets
- agent: I’ll work entirely through `docker exec` in the named container, inspect only the files inside `/app`, then compare the original and optimized query outputs on the provided SQLite DB.
- agent: I’m using the terminal-bench Harbor skill for the container workflow, then I’ll inspect the in-container SQL and schema before editing `/app/sol.sql`.
- command exit=0: /bin/zsh -lc 'docker exec -w /app tb21_codex_query_optimize_54955_20260603t191808 ls -la /app'
  output: total 49432 drwxr-xr-x 1 root root 4096 Jun 3 11:19 . drwxr-xr-x 1 root root 4096 Jun 3 11:19 .. -rw-r--r-- 1 root root 1158 May 26 07:21 my-sql-query.sql -r--r--r-- 1 root root 50606080 Jun 3 11:18 oewn.sqlite
- command exit=0: /bin/zsh -lc 'docker exec -w /app tb21_codex_query_optimize_54955_20260603t191808 sqlite3 /app/oewn.sqlite .tables'
  output: adjpositions morphs senses_vframes casedwords poses senses_vtemplates domains pronunciations synsets ilis relations usages lexes samples vframes lexes_morphs semrelations vtemplates lexes_pronunciations senses wikidatas lexrelations senses_adjpositions words
- command exit=0: /bin/zsh -lc "docker exec -w /app tb21_codex_query_optimize_54955_20260603t191808 sqlite3 /app/oewn.sqlite '.schema words'"
  output: CREATE TABLE `words` ( `wordid` INT NOT NULL, `word` VARCHAR(80) NOT NULL );
- command exit=0: /bin/zsh -lc "docker exec -w /app tb21_codex_query_optimize_54955_20260603t191808 sqlite3 /app/oewn.sqlite '.schema senses'"
  output: CREATE TABLE `senses` ( `senseid` INT NOT NULL, `sensekey` VARCHAR(100) DEFAULT NULL, `synsetid` INT NOT NULL, `luid` INT NOT NULL, `wordid` INT NOT NULL, `casedwordid` INT DEFAULT NULL, `lexid` INT NOT NULL, `sensenum` INT DEFAULT NULL, `tagcount` INT DEFAULT NULL );
- command exit=0: /bin/zsh -lc "docker exec -w /app tb21_codex_query_optimize_54955_20260603t191808 sqlite3 /app/oewn.sqlite '.indexes senses'"
- command exit=0: /bin/zsh -lc "docker exec -w /app tb21_codex_query_optimize_54955_20260603t191808 sqlite3 /app/oewn.sqlite '.schema synsets'"
  output: CREATE TABLE `synsets` ( `synsetid` INT NOT NULL, `posid` CHARACTER (1) CHECK( `posid` IN ('n','v','a','r','s') ) NOT NULL, `domainid` INT NOT NULL, `definition` MEDIUMTEXT NOT NULL );

## Use policy
- Treat these as examples from a previous successful run, not as new task requirements.
- Reuse snippets only when they match the live task contract and artifact path.
- Verify the final artifact in the live environment before stopping.
