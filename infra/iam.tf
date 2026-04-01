# ECS task execution role (ECR pull, CloudWatch logs, Secrets Manager)
resource "aws_iam_role" "ecs_execution" {
  name = "specmap-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_ecr" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "specmap-secrets-access"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Resource = [
        aws_secretsmanager_secret.session_secret.arn,
        aws_secretsmanager_secret.encryption_key.arn,
        aws_secretsmanager_secret.github_client_secret.arn,
        aws_secretsmanager_secret.github_webhook_secret.arn,
        aws_secretsmanager_secret.github_private_key.arn,
        aws_secretsmanager_secret.database_url.arn,
      ]
    }]
  })
}

# ECS task role (for application-level AWS API calls — empty for now)
resource "aws_iam_role" "ecs_task" {
  name = "specmap-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}
