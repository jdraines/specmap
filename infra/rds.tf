resource "aws_db_subnet_group" "main" {
  name       = "specmap"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = { Name = "specmap" }
}

resource "aws_db_instance" "main" {
  identifier = "specmap"

  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "specmap"
  username = "specmap"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period  = 7
  delete_automated_backups = true
  skip_final_snapshot      = false
  final_snapshot_identifier = "specmap-final"
  deletion_protection      = true

  tags = { Name = "specmap" }
}
