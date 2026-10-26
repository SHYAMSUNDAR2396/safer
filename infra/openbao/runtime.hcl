# Runtime can wrap/unwrap only this key. No list, rotate, config, delete or root rights.
path "transit/encrypt/safer-data" { capabilities = ["update"] }
path "transit/decrypt/safer-data" { capabilities = ["update"] }
