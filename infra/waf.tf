resource "aws_wafv2_web_acl" "main" {
  name        = "specmap"
  description = "Rate limiting for specmap"
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 500
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "specmap-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "specmap-waf"
    sampled_requests_enabled   = true
  }

  tags = { Name = "specmap" }
}
