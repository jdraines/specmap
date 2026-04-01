terraform {
  required_version = ">= 1.5"

  backend "s3" {
    bucket         = "specmap-terraform-state"
    key            = "specmap/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "specmap-terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = "specmap"
      ManagedBy = "terraform"
    }
  }
}
