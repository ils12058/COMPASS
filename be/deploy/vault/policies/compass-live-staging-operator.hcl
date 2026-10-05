# Privileged human operator, never assigned to the runtime AppRole or containers.
path "kv/data/compass/live-staging/*" {
  capabilities = ["create", "read", "update"]
}
path "kv/metadata/compass/live-staging/*" {
  capabilities = ["read", "list"]
}
path "auth/approle/role/compass-live-staging-runtime" {
  capabilities = ["create", "read", "update"]
}
path "auth/approle/role/compass-live-staging-runtime/role-id" {
  capabilities = ["read"]
}
path "auth/approle/role/compass-live-staging-runtime/secret-id" {
  capabilities = ["create", "update"]
}
path "auth/approle/role/compass-live-staging-runtime/secret-id-accessor/destroy" {
  capabilities = ["update"]
}
path "sys/storage/raft/snapshot" {
  capabilities = ["read", "update"]
}
# Forced restores and changing auth/policies remain an exceptional recovery/bootstrap operation.
