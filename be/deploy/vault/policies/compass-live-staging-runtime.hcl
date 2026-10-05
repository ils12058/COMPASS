# Runtime values only. No metadata/list, demo, write, delete, or administration grants.
path "kv/data/compass/live-staging/core" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/database/postgres" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/database/redis" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/storage/s3" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/mail/smtp" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/integrations/turnstile" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/integrations/daily" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/integrations/psgc" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/authentication/totp" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/confidential-data/routine-interview" {
  capabilities = ["read"]
}
path "kv/data/compass/live-staging/notifications/web-push" {
  capabilities = ["read"]
}
# The Agent may inspect and renew only its own service token.
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
path "auth/token/renew-self" {
  capabilities = ["update"]
}
