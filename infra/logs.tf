resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/specmap"
  retention_in_days = 30

  tags = { Name = "specmap" }
}
