ui = false
storage "raft" {
  node_id = "safer-local-readiness"
  path = "/bao/data"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = 1
}
cluster_addr = "https://127.0.0.1:8201"
api_addr = "http://127.0.0.1:58200"
