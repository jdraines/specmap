# Secret "shells" — Terraform creates the resources, values are populated
# manually via: aws secretsmanager put-secret-value --secret-id <name> --secret-string '<value>'

resource "aws_secretsmanager_secret" "session_secret" {
  name = "specmap/session-secret"
  tags = { Name = "specmap-session-secret" }
}

resource "aws_secretsmanager_secret" "encryption_key" {
  name = "specmap/encryption-key"
  tags = { Name = "specmap-encryption-key" }
}

resource "aws_secretsmanager_secret" "github_client_secret" {
  name = "specmap/github-client-secret"
  tags = { Name = "specmap-github-client-secret" }
}

resource "aws_secretsmanager_secret" "github_webhook_secret" {
  name = "specmap/github-webhook-secret"
  tags = { Name = "specmap-github-webhook-secret" }
}

resource "aws_secretsmanager_secret" "github_private_key" {
  name = "specmap/github-private-key"
  tags = { Name = "specmap-github-private-key" }
}

resource "aws_secretsmanager_secret" "database_url" {
  name = "specmap/database-url"
  tags = { Name = "specmap-database-url" }
}
