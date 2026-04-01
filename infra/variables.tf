variable "domain_name" {
  description = "Primary domain name (e.g. specmap.example.com)"
  type        = string
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for the domain"
  type        = string
}

variable "github_client_id" {
  description = "GitHub OAuth App client ID"
  type        = string
}

variable "github_app_id" {
  description = "GitHub App ID"
  type        = string
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Email address for budget alerts"
  type        = string
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "ecs_max_count" {
  description = "Maximum number of ECS tasks for auto-scaling"
  type        = number
  default     = 3
}
