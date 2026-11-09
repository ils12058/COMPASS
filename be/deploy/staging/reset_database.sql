-- psql identifiers are server-quoted; connect to maintenance DB postgres, never the target.
SELECT :'database' NOT IN ('postgres', 'template0', 'template1')
       AND length(:'database') > 0 AND length(:'owner') > 0 AS allowed \gset
\if :allowed
SELECT format('DROP DATABASE IF EXISTS %I WITH (FORCE)', :'database') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'database', :'owner') \gexec
\else
\quit 3
\endif
