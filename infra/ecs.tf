resource "aws_ecs_cluster" "main" {
  name = "specmap"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = { Name = "specmap" }
}

resource "aws_ecs_task_definition" "main" {
  family                   = "specmap"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256  # 0.25 vCPU
  memory                   = 512  # 0.5 GB
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "specmap"
    image     = "${aws_ecr_repository.main.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]

    environment = [
      { name = "PORT", value = "8080" },
      { name = "BASE_URL", value = "https://${var.domain_name}" },
      { name = "GITHUB_CLIENT_ID", value = var.github_client_id },
      { name = "GITHUB_APP_ID", value = var.github_app_id },
    ]

    secrets = [
      { name = "SESSION_SECRET", valueFrom = aws_secretsmanager_secret.session_secret.arn },
      { name = "ENCRYPTION_KEY", valueFrom = aws_secretsmanager_secret.encryption_key.arn },
      { name = "GITHUB_CLIENT_SECRET", valueFrom = aws_secretsmanager_secret.github_client_secret.arn },
      { name = "GITHUB_WEBHOOK_SECRET", valueFrom = aws_secretsmanager_secret.github_webhook_secret.arn },
      { name = "GITHUB_PRIVATE_KEY", valueFrom = aws_secretsmanager_secret.github_private_key.arn },
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
    ]

    healthCheck = {
      command     = ["CMD-SHELL", "wget -qO- http://localhost:8080/healthz || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 10
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = "us-east-1"
        "awslogs-stream-prefix" = "specmap"
      }
    }
  }])

  tags = { Name = "specmap" }
}

resource "aws_ecs_service" "main" {
  name            = "specmap"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = "specmap"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener.https]

  lifecycle {
    ignore_changes = [desired_count]
  }
}

# --- Auto-scaling ---

resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = var.ecs_max_count
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.main.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "ecs_cpu" {
  name               = "specmap-cpu-tracking"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
